package main

import (
	"fmt"
	"log"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func forwardMain() {
	lambda.Start(func(e events.S3Event) {
		for _, record := range e.Records {
			switch record.EventName {
			case "CREATED":
				if err := handleCreate(record.S3); err != nil {
					log.Println("Handling create:", err)
				}
			default:
				log.Println("Unknown event name:", record.EventName)
			}
		}
	})
}

func handleCreate(entity events.S3Entity) error {
	message, err := DownloadMessage(entity.Bucket.Name, entity.Object.Key)
	if err != nil {
		return fmt.Errorf("Downloading message: %w", err)
	}

	account, err := GetAccountFromID(message.RecipientID())
	if err != nil {
		return fmt.Errorf("Looking up account: %w", err)
	}

	if err = message.Forward(account.RecipientAddresses()); err != nil {
		return fmt.Errorf("Fowarding message: %w", err)
	}

	return nil
}
