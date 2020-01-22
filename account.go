package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/dynamodb"
	"github.com/aws/aws-sdk-go/service/dynamodb/dynamodbattribute"
	"github.com/aws/aws-sdk-go/service/ses"
	uuid "github.com/satori/go.uuid"
)

var (
	// ErrAccountNotFound indicates that an account does not exist.
	ErrAccountNotFound = errors.New("Account not found")

	accountsTable = os.Getenv("ACCOUNTS_TABLE")
	introTemplate = os.Getenv("INTRO_TEMPLATE")
	ruleName      = os.Getenv("RECEIVE_RULE")
	ruleSetName   = os.Getenv("RULESET_NAME")
)

// recipient is an account's recipient.
type recipient struct {
	address string
	token   string
}

// Account is a forwarding email account.
type Account struct {
	id         string
	expires    int64
	recipients []recipient
}

// NewAccount creates a new account and inserts it into the database.
func NewAccount(recipients []string, duration time.Duration) (*Account, error) {
	account := &Account{
		id:      uuid.NewV4().String(),
		expires: time.Now().Add(duration).Unix(),
	}

	for _, address := range recipients {
		account.recipients = append(account.recipients, recipient{
			address: address,
			token:   uuid.NewV4().String(),
		})
	}

	item, err := dynamodbattribute.MarshalMap(account)
	if err != nil {
		return nil, err
	}

	if _, err = awsDDB.PutItem(&dynamodb.PutItemInput{
		TableName: aws.String(accountsTable),
		Item:      item,
	}); err != nil {
		return nil, err
	}

	return account, nil
}

// GetAccountFromID gets an account from an ID.
func GetAccountFromID(id string) (*Account, error) {
	result, err := awsDDB.GetItem(&dynamodb.GetItemInput{
		TableName: aws.String(accountsTable),
		Key: map[string]*dynamodb.AttributeValue{
			"id": {
				S: aws.String(id),
			},
		},
	})
	if err != nil {
		return nil, err
	}

	var account *Account
	if err = dynamodbattribute.UnmarshalMap(result.Item, account); err != nil {
		return nil, err
	}

	if account.id == "" {
		return nil, ErrAccountNotFound
	}

	return account, nil
}

// GetAccountFromStream gets an account from a DynamoDB stream image.
func GetAccountFromStream(image map[string]events.DynamoDBAttributeValue) (*Account, error) {
	account := &Account{
		id: image["id"].String(),
	}

	var err error
	if account.expires, err = image["expires"].Integer(); err != nil {
		return nil, err
	}

	for _, r := range image["recipients"].List() {
		dict := r.Map()
		account.recipients = append(account.recipients, recipient{
			address: dict["address"].String(),
			token:   dict["token"].String(),
		})
	}

	return account, nil
}

// Address returns the account's email address.
func (a Account) Address() string {
	return fmt.Sprintf("%s@%s", a.id, domain)
}

// Activate activates the account so that it begins receiving and forwarding emails.
func (a Account) Activate() error {
	rule, err := getReceiptRule()
	if err != nil {
		return err
	}

	rule.Recipients = append(rule.Recipients, aws.String(a.Address()))

	return updateReceiptRule(rule)
}

// RecipientAddresses gets the account's recipient addresses.
func (a Account) RecipientAddresses() []string {
	addresses := []string{}
	for _, r := range a.recipients {
		addresses = append(addresses, r.address)
	}
	return addresses
}

// Deactivate deactivates the account so that it stops receiving and forwarding emails.
func (a Account) Deactivate() error {
	rule, err := getReceiptRule()
	if err != nil {
		return err
	}

	recipients := []*string{}
	for _, recipient := range rule.Recipients {
		if *recipient != a.Address() {
			recipients = append(recipients, recipient)
		}
	}
	rule.Recipients = recipients

	return updateReceiptRule(rule)
}

// Notify sends the introduction email notification to all recipients.
func (a Account) Notify() error {
	// TODO: If there are >50 recipients, do multiple calls.
	defaultData, err := json.Marshal(map[string]string{
		"id": a.id,
	})
	if err != nil {
		return err
	}

	destinations := []*ses.BulkEmailDestination{}
	for _, recipient := range a.recipients {
		var data []byte
		if data, err = json.Marshal(map[string]string{
			"token": recipient.token,
		}); err != nil {
			return err
		}

		destinations = append(destinations, &ses.BulkEmailDestination{
			Destination: &ses.Destination{
				ToAddresses: []*string{
					aws.String(recipient.address),
				},
			},
			ReplacementTemplateData: aws.String(string(data)),
		})
	}

	if _, err = awsSES.SendBulkTemplatedEmail(&ses.SendBulkTemplatedEmailInput{
		Source:              aws.String(fmt.Sprintf("noreply@%s", domain)),
		Template:            aws.String(introTemplate),
		DefaultTemplateData: aws.String(string(defaultData)),
		Destinations:        destinations,
	}); err != nil {
		return err
	}

	return nil
}

// GetRecipientByToken looks up a recipient by their unsubscribe token and returns their address.
func (a Account) GetRecipientByToken(token string) (string, bool) {
	for _, r := range a.recipients {
		if r.token == token {
			return r.address, true
		}
	}
	return "", false
}

// RemoveRecipient removes a recipient from the account's recipient list.
func (a *Account) RemoveRecipient(address string) error {
	found := false
	recipients := []recipient{}
	updates := []*dynamodb.AttributeValue{}
	for _, recipient := range a.recipients {
		if recipient.address == address {
			found = true
		} else {
			recipients = append(recipients, recipient)

			update, err := dynamodbattribute.Marshal(recipient)
			if err != nil {
				return err
			}
			updates = append(updates, update)
		}
	}

	if !found {
		return nil
	}

	if _, err := awsDDB.UpdateItem(&dynamodb.UpdateItemInput{
		TableName: aws.String(accountsTable),
		Key: map[string]*dynamodb.AttributeValue{
			"id": {
				S: aws.String(a.id),
			},
		},
		ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
			":rs": {
				L: updates,
			},
		},
		UpdateExpression: aws.String("set recipients = :rs"),
	}); err != nil {
		return err
	}

	a.recipients = recipients

	return nil
}

// getReceiptRule gets the receipt rule.
func getReceiptRule() (*ses.ReceiptRule, error) {
	resp, err := awsSES.DescribeReceiptRule(&ses.DescribeReceiptRuleInput{
		RuleName:    aws.String(ruleName),
		RuleSetName: aws.String(ruleSetName),
	})
	if err != nil {
		return nil, err
	}

	return resp.Rule, nil
}

// updateReceiptRule saves the receipt rule with its current state.
func updateReceiptRule(rule *ses.ReceiptRule) error {
	_, err := awsSES.UpdateReceiptRule(&ses.UpdateReceiptRuleInput{
		Rule:        rule,
		RuleSetName: aws.String(ruleSetName),
	})

	return err

}
