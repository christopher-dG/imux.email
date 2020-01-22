package main

import (
	"fmt"
	"net/url"
	"os"
	"time"

	"github.com/stripe/stripe-go"
	"github.com/stripe/stripe-go/checkout/session"
)

const (
	statePending   = "PENDING"
	stateCancelled = "CANCELLED"
	stateSuccess   = "SUCCESS"
)

var successMessage = url.QueryEscape("Thanks for ordering! Check your email for further information.")

func init() {
	stripe.Key = os.Getenv("STRIPE_PRIVATE_KEY")
}

type Order struct {
	id         string
	recipients []string
	weeks      int
	price      int64
	state      string
	account    *string
}

func (a Order) ID() string {
	return a.id
}

func NewOrder(recipients []string, weeks int) (*Order, error) {
	price := calculatePrice(len(recipients), weeks)
	sess, err := session.New(&stripe.CheckoutSessionParams{
		SuccessURL: stripe.String(fmt.Sprintf("https://%s?message=%s", domain, successMessage)),
		CancelURL:  stripe.String(fmt.Sprintf("https://%s?cancelled=true", domain)),
		PaymentMethodTypes: stripe.StringSlice([]string{
			"card",
		}),
		LineItems: []*stripe.CheckoutSessionLineItemParams{
			&stripe.CheckoutSessionLineItemParams{
				Name:        stripe.String(fmt.Sprintf("Shared email address from %s", domain)),
				Description: stripe.String(fmt.Sprintf("Duration of %d recipients, %d weeks", len(recipients), weeks)),
				Amount:      stripe.Int64(price),
				Currency:    stripe.String("usd"),
				Quantity:    stripe.Int64(1),
			},
		},
	})
	if err != nil {
		return nil, err
	}

	order := &Order{
		id:         sess.ID,
		recipients: recipients,
		weeks:      weeks,
		price:      price,
		state:      statePending,
	}

	return order, nil
}

func GetOrderFromID(id string) (*Order, error) {
	return nil, nil
}

func (o *Order) OnCompleted() error {
	_, err := NewAccount(o.recipients, time.Hour*24*7*time.Duration(o.weeks))
	if err != nil {
		return fmt.Errorf("Creating account: %w", err)
	}
	// todo update status and account id
	return nil
}

func calculatePrice(recipients, weeks int) int64 {
	return 500 // TODO
}
