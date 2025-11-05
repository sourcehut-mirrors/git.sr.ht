package main

import (
	"log"
	"os"

	coreconfig "git.sr.ht/~sircmpwn/core-go/config"
	"git.sr.ht/~sircmpwn/core-go/crypto"
	"github.com/vaughan0/go-ini"
)

var (
	buildOrigin string
	config      ini.File
	logger      *log.Logger
	origin      string
	pgcs        string
)

func main() {
	log.SetFlags(0)
	logger.Printf("%v", os.Args)
	// The update hook is run on the update and post-update git hooks, and
	// also runs a third stage directly. The first two stages are
	// performance critical and take place while the user is blocked at
	// their terminal. The third stage is done in the background.
	switch os.Args[0] {
	case "hooks/pre-receive":
		receiveHook("GIT_PRE_RECEIVE")
	case "hooks/update":
		update()
	case "hooks/post-update":
		postUpdate()
	case "hooks/post-receive":
		receiveHook("GIT_POST_RECEIVE")
	default:
		log.Fatalf("Unknown git hook %s", os.Args[0])
	}
}

func init() {
	logf, err := os.OpenFile("/var/log/git.sr.ht-update-hook",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Warning: unable to open log file: %v "+
			"(using stderr instead)", err)
		logger = log.New(os.Stderr, os.Args[0]+" ", log.LstdFlags)
	} else {
		logger = log.New(logf, os.Args[0]+" ", log.LstdFlags)
	}

	config = coreconfig.LoadConfig()

	var ok bool
	origin, ok = config.Get("git.sr.ht", "origin")
	if !ok {
		logger.Fatalf("No origin configured for git.sr.ht")
	}
	pgcs, ok = config.Get("git.sr.ht", "connection-string")
	if !ok {
		logger.Fatalf("No connection string configured for git.sr.ht: %v", err)
	}

	buildOrigin, _ = config.Get("builds.sr.ht", "origin") // Optional

	crypto.InitCrypto(config)
}
