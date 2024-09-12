package main

import (
	"bytes"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"git.sr.ht/~sircmpwn/core-go/crypto"
	"github.com/google/uuid"
	"github.com/mattn/go-runewidth"
)

type UpdatedRefInput struct {
	Ref string `json:"ref"`
	Old string `json:"old"`
	New string `json:"new"`
}

type GitEventInput struct {
	RepositoryID int               `json:"repositoryID"`
	Event        string            `json:"event"`
	Updates      []UpdatedRefInput `json:"updates"`
}

type WebhookSubscription struct {
	Id     int
	Url    string
	Events string
}

// Note: unlike normal sr.ht services, we don't add webhook deliveries to the
// database until after the HTTP request has been completed, to reduce time
// spent blocking the user's terminal.
type WebhookDelivery struct {
	Headers         string
	Payload         string
	Response        string
	ResponseHeaders string
	ResponseStatus  int
	SubscriptionId  int
	UUID            string
	Url             string
}

type UpdatedRef struct {
	Tag  *AnnotatedTag `json:"annotated_tag",omitempty`
	Name string        `json:"name"`
	Old  *Commit       `json:"old"`
	New  *Commit       `json:"new"`
}

type WebhookPayload struct {
	Push     string            `json:"push"`
	PushOpts map[string]string `json:"push-options"`
	Pusher   UserContext       `json:"pusher"`
	Refs     []UpdatedRef      `json:"refs"`
}

var ansi = regexp.MustCompile("\x1B\\[[0-?]*[ -/]*[@-~]")

func deliverWebhooks(subs []WebhookSubscription,
	payload []byte, printResponse bool) []WebhookDelivery {

	var deliveries []WebhookDelivery
	client := &http.Client{Timeout: 5 * time.Second}

	for _, sub := range subs {
		nonce, signature := crypto.SignWebhook(payload)

		deliveryUuid := uuid.New().String()
		body := bytes.NewBuffer(payload)
		req, err := http.NewRequest("POST", sub.Url, body)
		req.Header.Add("Content-Type", "application/json")
		req.Header.Add("X-Webhook-Event", "repo:post-update")
		req.Header.Add("X-Webhook-Delivery", deliveryUuid)
		req.Header.Add("X-Payload-Nonce", nonce)
		req.Header.Add("X-Payload-Signature", signature)

		var requestHeaders bytes.Buffer
		for name, values := range req.Header {
			requestHeaders.WriteString(fmt.Sprintf("%s: %s\n",
				name, strings.Join(values, ", ")))
		}

		delivery := WebhookDelivery{
			Headers:        requestHeaders.String(),
			Payload:        string(payload),
			ResponseStatus: -1,
			SubscriptionId: sub.Id,
			UUID:           deliveryUuid,
			Url:            sub.Url,
		}

		resp, err := client.Do(req)
		if err != nil {
			delivery.Response = fmt.Sprintf("Error sending webhook: %v", err)
			log.Println(delivery.Response)
			deliveries = append(deliveries, delivery)
			continue
		}
		defer resp.Body.Close()
		respBody, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			delivery.Response = fmt.Sprintf("Error reading webhook "+
				"response: %v", err)
			log.Println(delivery.Response)
			deliveries = append(deliveries, delivery)
			continue
		}
		if !utf8.Valid(respBody) {
			delivery.Response = "Webhook response is not valid UTF-8"
			log.Println(delivery.Response)
			deliveries = append(deliveries, delivery)
			continue
		}
		if printResponse {
			u, _ := url.Parse(sub.Url) // Errors will have happened earlier
			log.Printf("Response from %s:", u.Host)
			log.Println(runewidth.Truncate(ansi.ReplaceAllString(
				string(respBody), ""), 1024, "..."))
		}
		logger.Printf("Delivered webhook to %s (sub %d), got %d",
			sub.Url, sub.Id, resp.StatusCode)

		var responseHeaders bytes.Buffer
		for name, values := range resp.Header {
			responseHeaders.WriteString(fmt.Sprintf("%s: %s\n",
				name, strings.Join(values, ", ")))
		}

		delivery.ResponseStatus = resp.StatusCode
		delivery.ResponseHeaders = responseHeaders.String()
		if len(respBody) > 65535 {
			delivery.Response = string(respBody)[:65535]
		} else {
			delivery.Response = string(respBody)
		}
		deliveries = append(deliveries, delivery)
	}

	return deliveries
}
