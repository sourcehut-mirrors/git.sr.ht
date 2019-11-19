package main

import (
	"log"
	"os"

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
	// The update hook is run on the update and post-update git hooks, and also
	// runs a third stage directly. The first two stages are performance
	// critical and take place while the user is blocked at their terminal. The
	// third stage is done in the background.
	if os.Args[0] == "hooks/update" {
		update()
	} else if os.Args[0] == "hooks/post-update" {
		postUpdate()
	} else if os.Args[0] == "stage-3" {
		stage3()
	} else {
		log.Fatalf("Unknown git hook %s", os.Args[0])
	}
}

func init() {
	logf, err := os.OpenFile("/var/log/gitsrht-update-hook",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Warning: unable to open log file: %v "+
			"(using stderr instead)", err)
		logger = log.New(os.Stderr, os.Args[0]+" ", log.LstdFlags)
	} else {
		logger = log.New(logf, os.Args[0]+" ", log.LstdFlags)
	}

	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		logger.Fatalf("Failed to load config file: %v", err)
	}

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
}
