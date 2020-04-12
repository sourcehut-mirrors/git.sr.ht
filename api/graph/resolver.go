package graph

//go:generate go run git.sr.ht/~sircmpwn/gqlgen

import (
	"database/sql"
)

type Resolver struct {
	DB *sql.DB
}
