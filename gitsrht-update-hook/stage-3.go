package main

import (
	"database/sql"
	"encoding/json"
	"os"

	_ "github.com/lib/pq"
)

func stage3() {
	var context PushContext
	contextJson, ctxOk := os.LookupEnv("SRHT_PUSH_CTX")
	pushUuid, pushOk := os.LookupEnv("SRHT_PUSH")
	if !ctxOk || !pushOk {
		logger.Fatal("Missing required variables in environment, " +
			"configuration error?")
	}

	logger.Printf("Running stage 3 for push %s", pushUuid)

	if err := json.Unmarshal([]byte(contextJson), &context); err != nil {
		logger.Fatalf("unmarshal SRHT_PUSH_CTX: %v", err)
	}

	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		logger.Fatalf("Failed to open a database connection: %v", err)
	}

	var subscriptions []WebhookSubscription
	var deliveries []WebhookDelivery
	if err := json.Unmarshal([]byte(os.Args[1]), &deliveries); err != nil {
		logger.Fatalf("Unable to unmarhsal delivery array: %v", err)
	}
	payload := []byte(os.Args[2])

	var rows *sql.Rows
	if rows, err = db.Query(`
			SELECT id, url, events
			FROM repo_webhook_subscription rws
			WHERE rws.repo_id = $1
				AND rws.events LIKE '%repo:post-update%'
				AND rws.sync = false`, context.Repo.Id); err != nil {
		logger.Fatalf("Error fetching webhooks: %v", err)
	}
	defer rows.Close()

	for i := 0; rows.Next(); i++ {
		var whs WebhookSubscription
		if err = rows.Scan(&whs.Id, &whs.Url, &whs.Events); err != nil {
			logger.Fatalf("Scanning webhook rows: %v", err)
		}
		subscriptions = append(subscriptions, whs)
	}

	deliveries = append(deliveries, deliverWebhooks(subscriptions, payload)...)
	for _, delivery := range deliveries {
		if _, err := db.Exec(`
			INSERT INTO repo_webhook_delivery (
				uuid,
				created,
				event,
				url,
				payload,
				payload_headers,
				response,
				response_status,
				response_headers,
				subscription_id
			) VALUES (
				$1, NOW() AT TIME ZONE 'UTC', 'repo:post-update',
				$2, $3, $4, $5, $6, $7
			);
		`, delivery.UUID, delivery.Url,
			delivery.Payload, delivery.Headers,
			delivery.Response, delivery.ResponseStatus, delivery.ResponseHeaders,
			delivery.SubscriptionId); err != nil {

			logger.Fatalf("Error inserting webhook delivery: %v", err)
		}
	}
}
