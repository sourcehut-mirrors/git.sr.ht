package main

import (
	"bytes"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"
	"github.com/mattn/go-runewidth"
	"golang.org/x/crypto/ed25519"
)

var (
	privkey ed25519.PrivateKey
)

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

func initWebhookKey() {
	b64key, ok := config.Get("webhooks", "private-key")
	if !ok {
		logger.Fatalf("No webhook key configured")
	}
	seed, err := base64.StdEncoding.DecodeString(b64key)
	if err != nil {
		logger.Fatalf("base64 decode webhooks private key: %v", err)
	}
	privkey = ed25519.NewKeyFromSeed(seed)
}

func deliverWebhooks(subs []WebhookSubscription,
	payload []byte, printResponse bool) []WebhookDelivery {

	var deliveries []WebhookDelivery
	initWebhookKey()
	client := &http.Client{Timeout: 5 * time.Second}

	for _, sub := range subs {
		var (
			nonceSeed []byte
			nonceHex  []byte
		)
		_, err := rand.Read(nonceSeed)
		if err != nil {
			logger.Fatalf("generate nonce: %v", err)
		}
		hex.Encode(nonceHex, nonceSeed)
		signature := ed25519.Sign(privkey, append(payload, nonceHex...))

		deliveryUuid := uuid.New().String()
		body := bytes.NewBuffer(payload)
		req, err := http.NewRequest("POST", sub.Url, body)
		req.Header.Add("Content-Type", "application/json")
		req.Header.Add("X-Webhook-Event", "repo:post-update")
		req.Header.Add("X-Webhook-Delivery", deliveryUuid)
		req.Header.Add("X-Payload-Nonce", string(nonceHex))
		req.Header.Add("X-Payload-Signature",
			base64.StdEncoding.EncodeToString(signature))

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
			delivery.Response = fmt.Sprintf("Error sending webhook: %v")
			log.Printf(delivery.Response)
			deliveries = append(deliveries, delivery)
			continue
		}
		defer resp.Body.Close()
		respBody, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			delivery.Response = fmt.Sprintf("Error reading webhook "+
				"response: %v", err)
			log.Printf(delivery.Response)
			deliveries = append(deliveries, delivery)
			continue
		}
		if !utf8.Valid(respBody) {
			delivery.Response = "Webhook response is not valid UTF-8"
			log.Printf(delivery.Response)
			deliveries = append(deliveries, delivery)
			continue
		}
		if printResponse {
			log.Println(runewidth.Truncate(string(respBody), 1024, "..."))
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
