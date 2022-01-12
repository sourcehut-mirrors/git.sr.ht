package webhooks

import (
	"context"
	"net/http"

	"git.sr.ht/~sircmpwn/core-go/webhooks"
	"github.com/99designs/gqlgen/graphql"
)

func NewQueue(schema graphql.ExecutableSchema) *webhooks.WebhookQueue {
	return webhooks.NewQueue(schema)
}

var webhooksCtxKey = &contextKey{"userWebhooks"}

func Middleware(queue *webhooks.WebhookQueue) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), webhooksCtxKey, queue)
			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}
