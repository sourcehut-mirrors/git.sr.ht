package graph

//go:generate go run github.com/99designs/gqlgen

import (
	"database/sql"
)

type Resolver struct {
	DB *sql.DB
}
