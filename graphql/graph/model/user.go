package model

import "time"

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

func (user *User) CanonicalName() string {
	return "~" + user.Username
}

func (user *User) Rows() string {
	return `
		"user".id,
		"user".created, "user".updated,
		"user".username,
		"user".email,
		"user".url,
		"user".location,
		"user".bio
	`
}

func (user *User) Fields() []interface{} {
	return []interface{}{
		&user.ID,
		&user.Created, &user.Updated,
		&user.Username,
		&user.Email,
		&user.URL,
		&user.Location,
		&user.Bio,
	}
}
