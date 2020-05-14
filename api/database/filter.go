package database

import (
	"strings"

	"github.com/google/shlex"
	sq "github.com/Masterminds/squirrel"
)

type KeyFunc func(sq.SelectBuilder, string) (string, error)

type SearchTerm struct {
	Key     string
	Value   string
	Inverse bool
}

type Searchable interface {
	Selectable

	// Update the select builder for bare search terms
	DefaultSearch(sq.SelectBuilder, string) (sq.SelectBuilder, error)

	// Return a map of KeyFuncs for each search key, whose values update the
	// select builder for the given search term
	//KeySearch() map[string]KeyFunc

	// Update the select builder for a key/value pair which is unknown
	//FallbackSearch(sq.SelectBuilder,
	//	key, value string) (sq.SelectBuilder, error)
}

func ApplyFilter(query sq.SelectBuilder, resource Searchable,
	search string) (sq.SelectBuilder, error) {
	terms, err := shlex.Split(search)
	if err != nil {
		return query, err
	}

	for _, term := range terms {
		parts := strings.SplitN(term, ":", 2)
		if len(parts) == 1 {
			query, err = resource.DefaultSearch(query, term)
			if err != nil {
				return query, err
			}
		}
	}

	return query, nil
}
