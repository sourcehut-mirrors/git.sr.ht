package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"

	"git.sr.ht/~sircmpwn/getopt"
	"git.sr.ht/~sircmpwn/gqlgen/graphql/handler"
	"git.sr.ht/~sircmpwn/gqlgen/graphql/playground"
	"github.com/go-chi/chi"
	"github.com/go-chi/chi/middleware"
	_ "github.com/lib/pq"
	"github.com/vaughan0/go-ini"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/crypto"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/generated"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
)

const defaultAddr = ":8080"

func main() {
	var (
		addr   string = defaultAddr
		config ini.File
		debug  bool
		err    error
	)
	opts, _, err := getopt.Getopts(os.Args, "b:d")
	if err != nil {
		panic(err)
	}
	for _, opt := range opts {
		switch opt.Option {
		case 'b':
			addr = opt.Value
		case 'd':
			debug = true
		}
	}

	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		log.Fatalf("Failed to load config file: %v", err)
	}

	crypto.InitCrypto(config)

	pgcs, ok := config.Get("git.sr.ht", "connection-string")
	if !ok {
		log.Fatalf("No connection string configured for git.sr.ht: %v", err)
	}

	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		log.Fatalf("Failed to open a database connection: %v", err)
	}

	router := chi.NewRouter()
	router.Use(auth.Middleware(db))
	router.Use(loaders.Middleware(db))
	router.Use(middleware.Logger)

	srv := handler.NewDefaultServer(generated.NewExecutableSchema(generated.Config{
		Resolvers: &graph.Resolver{DB: db},
	}))

	if debug {
		router.Handle("/", playground.Handler("GraphQL playground", "/query"))
	}
	router.Handle("/query", srv)

	log.Printf("running on %s", addr)
	log.Fatal(http.ListenAndServe(addr, router))
}
