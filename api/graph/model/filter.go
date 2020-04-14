package model

import (
	"fmt"
	"strings"

	"github.com/google/shlex"
	"github.com/lib/pq"
)

type KeyFunc func(tbl, value string) (string, error)

type SearchTerm struct {
	Key     string
	Value   string
	Inverse bool
}

type Searchable interface {
	// Returns the default WHERE clause for a given search term with no key.
	Default(tbl, term string) (string, error)

	// Returns a map of search functions for a given key, where each function
	// returns the appropriate WHERE clause for searching with the given
	// string.
	Keys() map[string]KeyFunc

	// Returns a WHERE clause for a given search key and value, where the key
	// was not found in the Keys() map.
	Fallback(tbl, key, value string) (string, error)
}

type WhereClause struct {
	Clause     string
	Parameters []interface{}
}

// Returns a WHERE clause for the given fitler
func Where(query *string, tbl string, param int,
	resource Searchable) (*WhereClause, error) {
	if query == nil {
		return &WhereClause{"true /* No search terms */", nil}, nil
	}

	tbl = pq.QuoteIdentifier(tbl)
	terms, err := shlex.Split(*query)
	if err != nil {
		return nil, err
	}

	var (
		clauses []string
		params  []interface{}
	)
	for _, term := range terms {
		parts := strings.SplitN(term, ":", 2)
		variable := fmt.Sprintf("$%d", param)
		param += 1
		if len(parts) == 1 {
			clause, err := resource.Default(tbl, variable)
			if err != nil {
				return nil, err
			}
			clauses = append(clauses, fmt.Sprintf("(%s)", clause))
			params = append(params, term)
		}
	}

	return &WhereClause{strings.Join(clauses, " AND "), params}, nil
}
