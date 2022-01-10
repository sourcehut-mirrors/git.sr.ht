package model

import (
	"time"

	"git.sr.ht/~sircmpwn/core-go/database"
)

type User struct {
	ID       int       `json:"id"`
	Created  time.Time `json:"created"`
	Updated  time.Time `json:"updated"`
	Username string    `json:"username"`
	Email    string    `json:"email"`
	URL      *string   `json:"url"`
	Location *string   `json:"location"`
	Bio      *string   `json:"bio"`

	alias  string
	fields *database.ModelFields
}

func (User) IsEntity() {}

func (u *User) CanonicalName() string {
	return "~" + u.Username
}

func (u *User) As(alias string) *User {
	u.alias = alias
	return u
}

func (u *User) Alias() string {
	return u.alias
}

func (u *User) Table() string {
	return "user"
}

func (u *User) Fields() *database.ModelFields {
	if u.fields != nil {
		return u.fields
	}
	u.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{"id", "id", &u.ID},
			{"created", "created", &u.Created},
			{"updated", "updated", &u.Updated},
			{"username", "username", &u.Username},
			{"email", "email", &u.Email},
			{"url", "url", &u.URL},
			{"location", "location", &u.Location},
			{"bio", "bio", &u.Bio},

			// Always fetch:
			{"id", "", &u.ID},
			{"username", "", &u.Username},
		},
	}
	return u.fields
}
