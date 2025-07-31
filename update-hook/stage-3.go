package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"

	"git.sr.ht/~sircmpwn/core-go/objects"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
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
	defer db.Close()

	var subscriptions []WebhookSubscription
	var deliveries []WebhookDelivery
	deliveriesJsonLen, err := strconv.Atoi(os.Args[1])
	if err != nil {
		logger.Fatalf("deliveriesJson length \"%v\": %v", string(os.Args[1]), err)
	}
	deliveriesJson := make([]byte, deliveriesJsonLen)
	if read, err := os.Stdin.Read(deliveriesJson); read != len(deliveriesJson) {
		logger.Fatalf("Failed to read deliveries: %v, %v", read, err)
	}
	if err := json.Unmarshal(deliveriesJson, &deliveries); err != nil {
		logger.Fatalf("Unable to unmarhsal delivery array: %v", err)
	}

	payloadLen, err := strconv.Atoi(os.Args[2])
	if err != nil {
		logger.Fatalf("payload length \"%v\": %v", string(os.Args[2]), err)
	}
	payload := make([]byte, payloadLen)
	if read, err := os.Stdin.Read(payload); read != len(payload) {
		logger.Fatalf("Failed to read payload: %v, %v", read, err)
	}

	var decoded WebhookPayload
	err = json.Unmarshal(payload, &decoded)
	if err != nil {
		logger.Fatalf("Failed to decode payload: %v\n", err)
	}

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

	logger.Printf("Making %d deliveries and recording %d from stage 2",
		len(subscriptions), len(deliveries))

	deliveries = append(deliveries, deliverWebhooks(
		subscriptions, payload, false)...)
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
				$2, $3, $4, $5, $6, $7, $8
			);
		`, delivery.UUID, delivery.Url,
			delivery.Payload, delivery.Headers,
			delivery.Response, delivery.ResponseStatus, delivery.ResponseHeaders,
			delivery.SubscriptionId); err != nil {

			logger.Fatalf("Error inserting webhook delivery: %v", err)
		}
	}

	logger.Printf("Delivered %d webhooks, recorded %d deliveries",
		len(subscriptions), len(deliveries))

	if _, ok := config.Get("objects", "s3-upstream"); ok {
		deleteArtifacts(&context, db, &decoded)
	}
}

func deleteArtifacts(ctx *PushContext, db *sql.DB, payload *WebhookPayload) {
	s3bucket, _ := config.Get("git.sr.ht", "s3-bucket")
	s3prefix, _ := config.Get("git.sr.ht", "s3-prefix")

	sc, err := objects.NewClient(config)
	if err != nil {
		logger.Fatalf("Error connecting to S3: %e", err)
	}

	for _, ref := range payload.Refs {
		if ref.New != nil || ref.Old == nil {
			continue
		}

		var rows *sql.Rows
		if rows, err = db.Query(`
			DELETE FROM artifacts
			WHERE repo_id = $1 AND commit = $2
			RETURNING filename;`, ctx.Repo.Id, ref.Old.Id); err != nil {

			logger.Fatalf("Error fetching artifacts: %v", err)
		}
		defer rows.Close()

		for rows.Next() {
			var filename string
			if err = rows.Scan(&filename); err != nil {
				logger.Fatalf("Scanning artifact rows: %e", err)
			}
			s3key := filepath.Join(s3prefix, "artifacts",
				"~"+ctx.Repo.OwnerName, ctx.Repo.Name, filename)
			logger.Printf("Deleting S3 object %s:%s", s3bucket, s3key)

			_, err := sc.DeleteObject(context.Background(),
				&s3.DeleteObjectInput{
					Bucket: aws.String(s3bucket),
					Key:    aws.String(s3key),
				})
			if err != nil {
				logger.Printf("Error removing S3 object: %e", err)
			}
		}
	}
}
