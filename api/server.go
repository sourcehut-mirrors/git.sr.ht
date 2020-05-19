package main

import (
	"git.sr.ht/~sircmpwn/gql.sr.ht"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/api"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
)

func main() {
	appConfig := gql.LoadConfig(":5101")

	gqlConfig := api.Config{Resolvers: &graph.Resolver{}}
	graph.ApplyComplexity(&gqlConfig)
	schema := api.NewExecutableSchema(gqlConfig)

	router := gql.MakeRouter("git.sr.ht", appConfig, schema, loaders.Middleware)
	gql.ListenAndServe(router)
}
