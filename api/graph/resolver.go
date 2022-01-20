package graph

import (
	"context"
	"fmt"
	"regexp"

	"github.com/99designs/gqlgen/graphql"
	"github.com/vektah/gqlparser/v2/gqlerror"
)

type Resolver struct{}

var (
	repoNameRE = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)
)

func gqlErrorf(ctx context.Context, field string, message string, items ...interface{}) *gqlerror.Error {
	err := &gqlerror.Error{
		Message: fmt.Sprintf(message, items...),
		Path:    graphql.GetPath(ctx),
		Extensions: map[string]interface{}{
			"field": field,
		},
	}
	return err
}

var allowedCloneSchemes = map[string]struct{}{
	"https": struct{}{},
	"http":  struct{}{},
	"git":   struct{}{},
}
