package main

import (
	"fmt"
	"log"
	"os"
	"strconv"
)

func preReceive() {
	// TODO: This would be a good place to enforce branch update restrictions
	// and such, or to check OWNERS, etc.
	pushUuid, ok := os.LookupEnv("SRHT_PUSH")
	if !ok {
		logger.Fatal("Missing SRHT_PUSH in environment, configuration error?")
	}
	logger.Printf("Running pre-receive for push %s", pushUuid)

	if nopts, ok := os.LookupEnv("GIT_PUSH_OPTION_COUNT"); ok {
		n, _ := strconv.Atoi(nopts)
		configureOpts(pushUuid, n)
	}
}

func configureOpts(pushUuid string, nopts int) {
	for i := 0; i < nopts; i++ {
		opt := os.Getenv(fmt.Sprintf("GIT_PUSH_OPTION_%d", i))
		if opt == "debug" {
			log.Printf("debug: %s", pushUuid)
		}
	}
}
