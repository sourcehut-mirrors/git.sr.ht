package main

import (
	"fmt"
	"log"
	"os"
	"time"
	"unicode/utf8"

	goredis "github.com/go-redis/redis"
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

	if !utf8.ValidString(refname) {
		logger.Printf("Refusing ref '%s': not UTF-8", refname)
		log.Printf("%s not valid UTF-8, see https://github.com/libgit2/pygit2/issues/1028 for more information", refname)
		os.Exit(1)
	}

	redisHost, ok := config.Get("sr.ht", "redis-host")
	if !ok {
		redisHost = "redis://localhost:6379"
	}
	ropts, err := goredis.ParseURL(redisHost)
	if err != nil {
		logger.Fatalf("Failed to parse redis host: %v", err)
	}
	redis := goredis.NewClient(ropts)
	redis.Set(fmt.Sprintf("update.%s.%s", pushUuid, refname),
		fmt.Sprintf("%s:%s", oldref, newref), 10*time.Minute)
}
