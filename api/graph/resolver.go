package graph

import (
	"regexp"
)

type Resolver struct{}

var (
	repoNameRE = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)
)
