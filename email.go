package main

import (
	"fmt"
	"io/ioutil"
	"net/mail"
	"strings"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
)

// Message is an email message.
type Message mail.Message

// Forward forwards a message to some recipients.
func (m Message) Forward(recipients []string) error {
	// TODO

	bs, err := ioutil.ReadAll(m.Body)
	if err != nil {
		return fmt.Errorf("Reading message body: %w", err)
	}
	fmt.Println(string(bs))
	return nil
}

func (m Message) RecipientID() string {
	from := m.Header.Get("From")
	idx := strings.Index(from, "@")
	return from[:idx]
}

func DownloadMessage(bucket, key string) (*Message, error) {
	resp, err := awsS3.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	})
	if err != nil {
		return nil, err
	}

	message, err := mail.ReadMessage(resp.Body)
	if err != nil {
		return nil, err
	}

	converted := Message(*message)
	return &converted, nil
}
