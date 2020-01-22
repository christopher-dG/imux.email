package main

import (
	"fmt"
	"log"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func accountsMain() {
	lambda.Start(func(e events.DynamoDBEvent) error {
		for _, record := range e.Records {
			switch record.EventName {
			case "INSERT":
				if err := handleInsert(record.Change.NewImage); err != nil {
					log.Println("Handling insert:", err)
				}
			case "REMOVE":
				if err := handleRemove(record.Change.OldImage); err != nil {
					log.Println("Handling remove:", err)
				}
			default:
				log.Println("Unknown event name:", record.EventName)
			}
		}

		return nil
	})
}

func handleInsert(image map[string]events.DynamoDBAttributeValue) error {
	account, err := GetAccountFromStream(image)
	if err != nil {
		return fmt.Errorf("Constructing account: %w", err)
	}

	if err = account.Activate(); err != nil {
		return fmt.Errorf("Activating account: %w", err)
	}

	if err = account.Notify(); err != nil {
		return fmt.Errorf("Notifying recipients: %w", err)
	}

	return nil
}

func handleRemove(image map[string]events.DynamoDBAttributeValue) error {
	account, err := GetAccountFromStream(image)
	if err != nil {
		return fmt.Errorf("Constructing account: %w", err)
	}

	if err = account.Deactivate(); err != nil {
		return fmt.Errorf("Deactivating account: %w", err)
	}

	return nil

}
