package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"

	"github.com/go-chi/chi"
	"github.com/vaughan0/go-ini"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/loaders"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/graph"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/graph/generated"
	"git.sr.ht/~sircmpwn/gqlgen/graphql/handler"
	"git.sr.ht/~sircmpwn/gqlgen/graphql/playground"

	_ "github.com/lib/pq"
)

const defaultPort = "8080"

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = defaultPort
	}

	var (
		config ini.File
		err    error
	)
	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		log.Fatalf("Failed to load config file: %v", err)
	}

	pgcs, ok := config.Get("git.sr.ht", "connection-string")
	if !ok {
		log.Fatalf("No connection string configured for git.sr.ht: %v", err)
	}

	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		log.Fatalf("Failed to open a database connection: %v", err)
	}

	router := chi.NewRouter()
	// TODO: Add middleware to:
	// - Gracefully handle panics
	// - Log queries in debug mode
	router.Use(auth.Middleware(db))
	router.Use(loaders.Middleware(db))

	srv := handler.NewDefaultServer(generated.NewExecutableSchema(generated.Config{
		Resolvers: &graph.Resolver{DB: db},
	}))

	router.Handle("/", playground.Handler("GraphQL playground", "/query"))
	router.Handle("/query", srv)

	log.Printf("connect to http://localhost:%s/ for GraphQL playground", port)
	log.Fatal(http.ListenAndServe(":"+port, router))
}
