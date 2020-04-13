package model

import (
	"context"
	"strings"
	"time"
)

type User struct {
	ID            int           `json:"id"`
	Created       time.Time     `json:"created"`
	Updated       time.Time     `json:"updated"`
	Username      string        `json:"username"`
	Email         string        `json:"email"`
	URL           *string       `json:"url"`
	Location      *string       `json:"location"`
	Bio           *string       `json:"bio"`
}

func (User) IsEntity() {}

func (u *User) CanonicalName() string {
	return "~" + u.Username
}

func (u *User) Columns(ctx context.Context, tbl string) string {
	columns := ColumnsFor(ctx, map[string]string{
		"id": "id",
		"created": "created",
		"updated": "updated",
		"username": "username",
		"email": "email",
		"url": "url",
		"location": "location",
		"bio": "bio",
	}, tbl)
	return strings.Join(columns, ", ")
}

func (u *User) Fields(ctx context.Context) []interface{} {
	return FieldsFor(ctx, map[string]interface{}{
		"id": &u.ID,
		"created": &u.Created,
		"updated": &u.Updated,
		"username": &u.Username,
		"email": &u.Email,
		"url": &u.URL,
		"location": &u.Location,
		"bio": &u.Bio,
	})
}
