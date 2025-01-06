package main

import (
	"context"
	"fmt"
	"os"
	"time"

	goredis "github.com/go-redis/redis/v8"
)

// XXX: This is run once for every single ref that's pushed. If someone pushes
// lots of refs, it might be expensive. Needs to be tested.
func update() {
	var (
		refname string = os.Args[1]
		oldref  string = os.Args[2]
		newref  string = os.Args[3]
	)
	pushUuid, ok := os.LookupEnv("SRHT_PUSH")
	if !ok {
		logger.Fatal("Missing SRHT_PUSH in environment, configuration error?")
	}
	logger.Printf("Running update for push %s", pushUuid)

	redisHost, ok := config.Get("sr.ht", "redis-host")
	if !ok {
		redisHost = "redis://localhost:6379"
	}
	ropts, err := goredis.ParseURL(redisHost)
	if err != nil {
		logger.Fatalf("Failed to parse redis host: %v", err)
	}
	redis := goredis.NewClient(ropts)
	redis.Set(context.Background(), fmt.Sprintf("update.%s.%s", pushUuid, refname),
		fmt.Sprintf("%s:%s", oldref, newref), 10*time.Minute)
}
