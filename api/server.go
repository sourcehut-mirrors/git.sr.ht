package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"git.sr.ht/~sircmpwn/getopt"
	"github.com/99designs/gqlgen/graphql/playground"
	"github.com/99designs/gqlgen/handler"
	"github.com/go-chi/chi"
	"github.com/go-chi/chi/middleware"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/vaughan0/go-ini"
	_ "github.com/lib/pq"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/crypto"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/api"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
)

const defaultAddr = ":5101"

var (
	requestsProcessed = promauto.NewCounter(prometheus.CounterOpts{
		Name: "git_api_requests_processed_total",
		Help: "Total number of API requests processed",
	})
	requestDuration = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "git_api_request_duration_millis",
		Help:    "Duration of processed HTTP requests in milliseconds",
		Buckets: []float64{10, 20, 40, 80, 120, 300, 600, 900, 1800},
	})
)

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

	var timeout time.Duration
	if to, ok := config.Get("git.sr.ht::api", "max-duration"); ok {
		timeout, err = time.ParseDuration(to)
		if err != nil {
			panic(err)
		}
	} else {
		timeout = 3 * time.Second
	}

	router := chi.NewRouter()
	router.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			next.ServeHTTP(w, r)
			end := time.Now()
			elapsed := end.Sub(start)
			requestDuration.Observe(float64(elapsed.Milliseconds()))
			requestsProcessed.Inc()
		})
	})
	router.Use(auth.Middleware(db))
	router.Use(loaders.Middleware(db))
	router.Use(middleware.Logger)
	router.Use(middleware.Timeout(timeout))

	gqlConfig := api.Config{
		Resolvers: &graph.Resolver{DB: db},
	}
	graph.ApplyComplexity(&gqlConfig)

	var complexity int
	if limit, ok := config.Get("git.sr.ht::api", "max-complexity"); ok {
		complexity, err = strconv.Atoi(limit)
		if err != nil {
			panic(err)
		}
	} else {
		complexity = 100
	}

	srv := handler.GraphQL(
		api.NewExecutableSchema(gqlConfig),
		handler.ComplexityLimit(complexity),
		handler.RecoverFunc(graph.EmailRecover(config, debug)))

	router.Handle("/query", srv)
	router.Handle("/query/metrics", promhttp.Handler())

	if debug {
		router.Handle("/", playground.Handler("GraphQL playground", "/query"))
	}

	log.Printf("running on %s", addr)
	log.Fatal(http.ListenAndServe(addr, router))
}
