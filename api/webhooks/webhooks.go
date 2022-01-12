package webhooks

import (
	"context"
	"log"
	"time"

	"git.sr.ht/~sircmpwn/core-go/auth"
	"git.sr.ht/~sircmpwn/core-go/webhooks"
	sq "github.com/Masterminds/squirrel"
	"github.com/google/uuid"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
)

func deliverUserWebhook(ctx context.Context, event model.WebhookEvent,
	payload model.WebhookPayload, payloadUUID uuid.UUID) {
	q, ok := ctx.Value(webhooksCtxKey).(*webhooks.WebhookQueue)
	if !ok {
		log.Fatalf("No webhooks worker for this context")
	}
	userID := auth.ForContext(ctx).UserID
	query := sq.
		Select().
		From("gql_user_wh_sub sub").
		Where("sub.user_id = ?", userID)
	q.Schedule(ctx, query, "user", event.String(),
		payloadUUID, payload)
}

func DeliverRepoEvent(ctx context.Context,
	event model.WebhookEvent, repository *model.Repository) {
	payloadUUID := uuid.New()
	payload := model.RepositoryEvent{
		UUID:       payloadUUID.String(),
		Event:      event,
		Date:       time.Now().UTC(),
		Repository: repository,
	}
	deliverUserWebhook(ctx, event, &payload, payloadUUID)
}
