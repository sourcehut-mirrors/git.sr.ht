package main

import (
	"log"
	"os"
)

func preReceive() {
	// TODO: This would be a good place to enforce branch update restrictions
	// and such, or to check OWNERS, etc.
	pushUuid, ok := os.LookupEnv("SRHT_PUSH")
	if !ok {
		logger.Fatal("Missing SRHT_PUSH in environment, configuration error?")
	}
	logger.Printf("Running pre-receive for push %s", pushUuid)

	loadOptions()
	if _, ok := options["debug"]; ok {
		log.Printf("debug: %s", pushUuid)
	}
}
