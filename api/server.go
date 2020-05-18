package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/binary"
	"fmt"
	"log"
	"net/http"
	"net/mail"
	"os"
	"runtime"
	"strconv"
	"time"

	"git.sr.ht/~sircmpwn/getopt"
	"github.com/99designs/gqlgen/graphql"
	"github.com/99designs/gqlgen/graphql/playground"
	"github.com/99designs/gqlgen/handler"
	"github.com/go-chi/chi"
	"github.com/go-chi/chi/middleware"
	"github.com/martinlindhe/base36"
	"github.com/vaughan0/go-ini"
	_ "github.com/lib/pq"
	gomail "gopkg.in/mail.v2"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/crypto"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/api"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
)

const defaultAddr = ":5101"

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
		handler.RecoverFunc(func(ctx context.Context, origErr interface{}) error {
			if _, ok := origErr.(error); !ok {
				log.Printf("Unexpected error in recover: %v\n", origErr)
				return fmt.Errorf("internal system error")
			}
			stack := make([]byte, 32768) // 32 KiB
			i := runtime.Stack(stack, false)
			log.Println(string(stack[:i]))
			if debug {
				return fmt.Errorf("internal system error")
			}

			to, ok := config.Get("mail", "error-to")
			if !ok {
				return fmt.Errorf("internal system error")
			}
			from, _ := config.Get("mail", "error-from")
			portStr, ok := config.Get("mail", "smtp-port")
			if !ok {
				return fmt.Errorf("internal system error")
			}
			port, _ := strconv.Atoi(portStr)
			host, _ := config.Get("mail", "smtp-host")
			user, _ := config.Get("mail", "smtp-user")
			pass, _ := config.Get("mail", "smtp-password")

			m := gomail.NewMessage()
			sender, err := mail.ParseAddress(from)
			if err != nil {
				log.Fatalf("Failed to parse sender address")
			}
			m.SetAddressHeader("From", sender.Address, sender.Name)
			recipient, err := mail.ParseAddress(to)
			if err != nil {
				log.Fatalf("Failed to parse recipient address")
			}
			m.SetAddressHeader("To", recipient.Address, recipient.Name)
			m.SetHeader("Message-ID", GenerateMessageID())
			m.SetHeader("Subject", fmt.Sprintf(
				"[git.sr.ht] GraphQL query error: %v", origErr))

			quser := auth.ForContext(ctx)
			octx := graphql.GetOperationContext(ctx)

			m.SetBody("text/plain", fmt.Sprintf(`Error occured processing GraphQL request:

%v

When running the following query on behalf of %s <%s>:

%s

The following stack trace was produced:

%s`, origErr, quser.Username, quser.Email, octx.RawQuery, string(stack[:i])))

			d := gomail.NewDialer(host, port, user, pass)
			if err := d.DialAndSend(m); err != nil {
				log.Printf("Error sending email: %v\n", err)
			}
			return fmt.Errorf("internal system error")
		}))

	router.Handle("/query", srv)

	if debug {
		router.Handle("/", playground.Handler("GraphQL playground", "/query"))
	}

	log.Printf("running on %s", addr)
	log.Fatal(http.ListenAndServe(addr, router))
}

// Generates an RFC 2822-compliant Message-Id based on the informational draft
// "Recommendations for generating Message IDs", for lack of a better
// authoritative source.
func GenerateMessageID() string {
	var (
		now   bytes.Buffer
		nonce []byte = make([]byte, 8)
	)
	binary.Write(&now, binary.BigEndian, time.Now().UnixNano())
	rand.Read(nonce)
	hostname, err := os.Hostname()
	if err != nil {
		hostname = "localhost"
	}
	return fmt.Sprintf("<%s.%s@%s>",
		base36.EncodeBytes(now.Bytes()),
		base36.EncodeBytes(nonce),
		hostname)
}
