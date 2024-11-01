package model

import (
	"context"
	"database/sql"
	"fmt"
	"strconv"
	"time"

	"git.sr.ht/~sircmpwn/core-go/database"
	"git.sr.ht/~sircmpwn/core-go/model"
	sq "github.com/Masterminds/squirrel"
	"github.com/lib/pq"
)

type WebhookDelivery struct {
	UUID            string       `json:"uuid"`
	Date            time.Time    `json:"date"`
	Event           WebhookEvent `json:"event"`
	RequestBody     string       `json:"requestBody"`
	ResponseBody    *string      `json:"responseBody"`
	ResponseHeaders *string      `json:"responseHeaders"`
	ResponseStatus  *int         `json:"responseStatus"`

	ID             int
	SubscriptionID int
	Name           string

	alias  string
	fields *database.ModelFields
}

func (whd *WebhookDelivery) WithName(name string) *WebhookDelivery {
	whd.Name = name
	return whd
}

func (whd *WebhookDelivery) As(alias string) *WebhookDelivery {
	whd.alias = alias
	return whd
}

func (whd *WebhookDelivery) Alias() string {
	return whd.alias
}

func (whd *WebhookDelivery) Table() string {
	return "gql_" + whd.Name + "_wh_delivery"
}

func (whd *WebhookDelivery) Fields() *database.ModelFields {
	if whd.fields != nil {
		return whd.fields
	}
	whd.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{"uuid", "uuid", &whd.UUID},
			{"date", "date", &whd.Date},
			{"event", "event", &whd.Event},
			{"request_body", "requestBody", &whd.RequestBody},
			{"response_body", "responseBody", &whd.ResponseBody},
			{"response_headers", "responseHeaders", &whd.ResponseHeaders},
			{"response_status", "responseStatus", &whd.ResponseStatus},

			// Always fetch:
			{"id", "", &whd.ID},
			{"subscription_id", "", &whd.SubscriptionID},
		},
	}
	return whd.fields
}

func (whd *WebhookDelivery) QueryWithCursor(ctx context.Context,
	runner sq.BaseRunner, q sq.SelectBuilder,
	cur *model.Cursor) ([]*WebhookDelivery, *model.Cursor) {
	var (
		err  error
		rows *sql.Rows
	)

	if cur.Next != "" {
		next, _ := strconv.ParseInt(cur.Next, 10, 64)
		q = q.Where(database.WithAlias(whd.alias, "id")+"<= ?", next)
	}
	q = q.
		OrderBy(database.WithAlias(whd.alias, "id") + " DESC").
		Limit(uint64(cur.Count + 1))

	if rows, err = q.RunWith(runner).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var deliveries []*WebhookDelivery
	for rows.Next() {
		var delivery WebhookDelivery
		if err := rows.Scan(database.Scan(ctx, &delivery)...); err != nil {
			panic(err)
		}
		delivery.Name = whd.Name
		deliveries = append(deliveries, &delivery)
	}

	if len(deliveries) > cur.Count {
		cur = &model.Cursor{
			Count:  cur.Count,
			Next:   strconv.Itoa(deliveries[len(deliveries)-1].ID),
			Search: cur.Search,
		}
		deliveries = deliveries[:cur.Count]
	} else {
		cur = nil
	}

	return deliveries, cur
}

func (we *WebhookEvent) Scan(src interface{}) error {
	bytes, ok := src.([]uint8)
	if !ok {
		return fmt.Errorf("Unable to scan from %T into WebhookEvent", src)
	}
	*we = WebhookEvent(string(bytes))
	if !we.IsValid() {
		return fmt.Errorf("%s is not a valid WebhookEvent", string(bytes))
	}
	return nil
}

type UserWebhookSubscription struct {
	ID     int            `json:"id"`
	Events []WebhookEvent `json:"events"`
	Query  string         `json:"query"`
	URL    string         `json:"url"`

	UserID     int
	AuthMethod string
	ClientID   *string
	TokenHash  *string
	Expires    *time.Time
	Grants     *string
	NodeID     *string

	alias  string
	fields *database.ModelFields
}

func (UserWebhookSubscription) IsWebhookSubscription() {}

func (sub *UserWebhookSubscription) As(alias string) *UserWebhookSubscription {
	sub.alias = alias
	return sub
}

func (sub *UserWebhookSubscription) Alias() string {
	return sub.alias
}

func (sub *UserWebhookSubscription) Table() string {
	return "gql_user_wh_sub"
}

func (sub *UserWebhookSubscription) Fields() *database.ModelFields {
	if sub.fields != nil {
		return sub.fields
	}
	sub.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{"events", "events", pq.Array(&sub.Events)},
			{"url", "url", &sub.URL},

			// Always fetch:
			{"id", "", &sub.ID},
			{"query", "", &sub.Query},
			{"user_id", "", &sub.UserID},
			{"auth_method", "", &sub.AuthMethod},
			{"token_hash", "", &sub.TokenHash},
			{"client_id", "", &sub.ClientID},
			{"grants", "", &sub.Grants},
			{"expires", "", &sub.Expires},
			{"node_id", "", &sub.NodeID},
		},
	}
	return sub.fields
}

func (sub *UserWebhookSubscription) QueryWithCursor(ctx context.Context,
	runner sq.BaseRunner, q sq.SelectBuilder,
	cur *model.Cursor) ([]WebhookSubscription, *model.Cursor) {
	var (
		err  error
		rows *sql.Rows
	)

	if cur.Next != "" {
		next, _ := strconv.ParseInt(cur.Next, 10, 64)
		q = q.Where(database.WithAlias(sub.alias, "id")+"<= ?", next)
	}
	q = q.
		OrderBy(database.WithAlias(sub.alias, "id")).
		Limit(uint64(cur.Count + 1))

	if rows, err = q.RunWith(runner).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var (
		subs   []WebhookSubscription
		lastID int
	)
	for rows.Next() {
		var sub UserWebhookSubscription
		if err := rows.Scan(database.Scan(ctx, &sub)...); err != nil {
			panic(err)
		}
		subs = append(subs, &sub)
		lastID = sub.ID
	}

	if len(subs) > cur.Count {
		cur = &model.Cursor{
			Count:  cur.Count,
			Next:   strconv.Itoa(lastID),
			Search: cur.Search,
		}
		subs = subs[:cur.Count]
	} else {
		cur = nil
	}

	return subs, cur
}

type GitWebhookSubscription struct {
	ID     int            `json:"id"`
	Events []WebhookEvent `json:"events"`
	Query  string         `json:"query"`
	URL    string         `json:"url"`

	RepoID     int
	AuthMethod string
	ClientID   *string
	TokenHash  *string
	Expires    *time.Time
	Grants     *string
	NodeID     *string

	alias  string
	fields *database.ModelFields
}

func (GitWebhookSubscription) IsWebhookSubscription() {}

func (sub *GitWebhookSubscription) As(alias string) *GitWebhookSubscription {
	sub.alias = alias
	return sub
}

func (sub *GitWebhookSubscription) Alias() string {
	return sub.alias
}

func (sub *GitWebhookSubscription) Table() string {
	return "gql_git_wh_sub"
}

func (sub *GitWebhookSubscription) Fields() *database.ModelFields {
	if sub.fields != nil {
		return sub.fields
	}
	sub.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{"events", "events", pq.Array(&sub.Events)},
			{"url", "url", &sub.URL},

			// Always fetch:
			{"id", "", &sub.ID},
			{"query", "", &sub.Query},
			{"repo_id", "", &sub.RepoID},
			{"auth_method", "", &sub.AuthMethod},
			{"token_hash", "", &sub.TokenHash},
			{"client_id", "", &sub.ClientID},
			{"grants", "", &sub.Grants},
			{"expires", "", &sub.Expires},
			{"node_id", "", &sub.NodeID},
		},
	}
	return sub.fields
}

func (sub *GitWebhookSubscription) QueryWithCursor(ctx context.Context,
	runner sq.BaseRunner, q sq.SelectBuilder,
	cur *model.Cursor) ([]WebhookSubscription, *model.Cursor) {
	panic("TODO")
}
