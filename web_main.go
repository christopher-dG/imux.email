package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"io/ioutil"
	"log"
	"net/http"
	"net/url"

	"github.com/apex/gateway"
	"github.com/stripe/stripe-go"
	"github.com/stripe/stripe-go/webhook"
)

var (
	templates     = template.Must(template.ParseGlob(filepath.Join("templates", "*.html")))
	webhookSecret = os.Getenv("STRIPE_WEBHOOK_SECRET")
)

type templateData struct {
	Domain string
}

var defaultData = templateData{
	Domain: domain,
}

type indexData struct {
	templateData
	Message string
}

func webMain() {
	http.HandleFunc("/", index)
	http.HandleFunc("/success", orderConfirmation)
	http.HandleFunc("/unsubscribe/", unsubscribe)
	http.HandleFunc("/orders/", createOrder)
	http.HandleFunc("/orders/webhook/", ordersWebhook)
	log.Fatal(gateway.ListenAndServe(":3000", nil))
}

// index returns the index document.
func index(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	render(w, "index.html", indexData{
		Message:      r.URL.Query().Get("message"),
		templateData: defaultData,
	})
}

func orderConfirmation(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	render(w, "success.html", nil)
}

// unsubscribe unsubscribes a user.
func unsubscribe(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	id := query.Get("id")
	token := query.Get("token")

	log.Println("Looking up account:", id)
	account, err := GetAccountFromID(id)
	if err != nil {
		log.Println("Looking up account failed:", err)
		redirect(w, r, "/", map[string]string{
			"message": fmt.Sprintf("Account %s was not found.", account.Address()),
		})
		return
	}

	log.Println("Looking for recipient with token:", token)
	recipient, ok := account.GetRecipientByToken(token)
	if !ok {
		log.Println("Looking up recipient failed:", err)
		redirect(w, r, "/", map[string]string{
			"message": fmt.Sprintf("Recipient was not found."),
		})
		return
	}

	log.Printf("Unsubscribing %s from %s\n", recipient, account.Address())
	if err = account.RemoveRecipient(recipient); err != nil {
		log.Println("Removing recipient failed:", err)
		redirect(w, r, "/", map[string]string{
			"message": fmt.Sprintf("Unsubscribing failed, please try again later."),
		})
		return
	}
}

// createOrder creates an order.
func createOrder(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	if err := r.ParseForm(); err != nil {
		log.Println("Parsing form failed:", err)
		redirect(w, r, "/", map[string]string{
			"message": "Invalid form input.",
		})
		return
	}

	weeks, err := strconv.Atoi(r.PostForm.Get("weeks"))
	if err != nil || weeks <= 0 {
		log.Println("Invalid weeks input:", err)
		redirect(w, r, "/", map[string]string{
			"message": "Invalid input for weeks.",
		})
		return
	}
	log.Println("Weeks:', weeks")

	recipients := []string{}
	for _, recipient := range r.PostForm["recipients"] {
		if strings.Contains(recipient, "@") {
			recipients = append(recipients, recipient)
		} else if len(recipient) > 0 {
			log.Println("Invalid email address:", recipient)
			redirect(w, r, "/", map[string]string{
				"message": fmt.Sprintf("Invalid email address %s.", recipient),
			})
			return
		}
	}
	log.Println("Recipients:", strings.Join(recipients, ", "))

	order, err := NewOrder(recipients, weeks)
	if err != nil {
		log.Println("Creating order failed:", err)
		redirect(w, r, "/", map[string]string{
			"message": "Failed to create the order, sorry!",
		})
		return
	}
	log.Println("Order ID:", order.ID())

	render(w, "redirect.html", map[string]string{
		"id": order.ID(),
	})
}

// ordersWebhook responds to a Stripe webhook.
func ordersWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	bs, err := ioutil.ReadAll(r.Body)
	if err != nil {
		log.Println("Reading request body failed:", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	event, err := webhook.ConstructEvent(bs, r.Header.Get("HTTP_STRIPE_SIGNATURE"), webhookSecret)
	if err != nil {
		log.Println("Constructing event failed:", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	if event.Type != "checkout.session.completed" {
		log.Println("Unknown event type:", event.Type)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	var session stripe.CheckoutSession
	if err = json.Unmarshal(event.Data.Raw, &session); err != nil {
		log.Println("Unmarshalling CheckoutSession failed:", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	log.Println("Looking up order:", session.ID)
	order, err := GetOrderFromID(session.ID)
	if err != nil {
		log.Println("Looking up order failed:", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	log.Println("Fulfiling order:", order.ID())
	if err = order.OnCompleted(); err != nil {
		log.Println("Processing webhook failed:", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}

func redirect(w http.ResponseWriter, r *http.Request, path string, query map[string]string) {
	values := url.Values{}
	for k, v := range query {
		values.Add(k, v)
	}

	http.Redirect(w, r, fmt.Sprintf("%s?%s", path, values.Encode()), http.StatusFound)
}

// render renders a template.
func render(w http.ResponseWriter, name string, data interface{}) {
	if err := templates.ExecuteTemplate(w, name, data); err != nil {
		log.Println("Rendering template failed:", err)
		http.Error(w, "Rendering template failed", http.StatusInternalServerError)
		return
	}
}
