package main

import (
	"fmt"
	"io"
	"log"
	"os"
	osuser "os/user"
	"strconv"
	"strings"
	"syscall"

	"github.com/vaughan0/go-ini"
)

type Dispatcher struct {
	cmd  string
	uid  int
	gid  int
	gids []int
}

func main() {
	var (
		config ini.File
		err    error
		logger *log.Logger
	)

	logf, err := os.OpenFile("/var/log/gitsrht-dispatch",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Warning: unable to open log file: %v "+
			"(using stderr instead)", err)
		logger = log.New(os.Stderr, "", log.LstdFlags)
	} else {
		logger = log.New(logf, "", log.LstdFlags)
	}

	logger.Println("Running git.sr.ht dispatch")

	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		logger.Fatalf("Failed to load config file: %v", err)
	}

	if len(os.Args) != 5 {
		logger.Fatalf(`Error: This command should be run by sshd's AuthorizedKeysCommand:

AuthorizedKeysCommand=%s "%%u" "%%h" "%%t" "%%k"
AuthorizedKeysCommandUser=root`, os.Args[0])
	}

	// Map uid -> dispatcher
	dispatchers := make(map[int]Dispatcher)
	for cmd, value := range config.Section("git.sr.ht::dispatch") {
		spec := strings.Split(value, ":")
		if len(spec) != 2 {
			logger.Fatalf("Expected %s=user:group", cmd)
		}
		user, err := osuser.Lookup(spec[0])
		if err != nil {
			logger.Fatalf("Error looking up user %s: %v", spec[0], err)
		}
		group, err := osuser.LookupGroup(spec[1])
		if err != nil {
			logger.Fatalf("Error looking up group %s: %v", spec[1], err)
		}
		groups, err := user.GroupIds()
		if err != nil {
			logger.Fatalf("Error looking up supplementary groups of user %s: %v", spec[0], err)
		}
		gids := make([]int, len(groups))
		for i, grp := range groups {
			sgid, _ := strconv.Atoi(grp)
			gids[i] = sgid
		}
		uid, _ := strconv.Atoi(user.Uid)
		gid, _ := strconv.Atoi(group.Gid)
		dispatchers[uid] = Dispatcher{cmd, uid, gid, gids}
		logger.Printf("Registered dispatcher for %s(%d):%s(%d):(%s): %s",
			spec[0], uid, spec[1], gid, strings.Join(groups, ","), cmd)
	}

	var user *osuser.User
	username := os.Args[1]
	if user, err = osuser.Lookup(username); err != nil {
		logger.Fatalf("Unknown user %s", username)
	}
	homedir := os.Args[2]
	key_type := os.Args[3]
	b64key := os.Args[4]
	authorized_keys_file := fmt.Sprintf("%s/.ssh/authorized_keys", homedir)
	uid, _ := strconv.Atoi(user.Uid)

	logger.Printf("Authorizing user %s (%d); home=%s; b64key=%s; key_type=%s",
		username, uid, homedir, b64key, key_type)

	if dispatcher, ok := dispatchers[uid]; ok {
		logger.Printf("Dispatching to %s", dispatcher.cmd)
		syscall.Setgroups(dispatcher.gids)
		syscall.Setgid(dispatcher.gid)
		syscall.Setuid(dispatcher.uid)
		if err := syscall.Exec(dispatcher.cmd, append([]string{
			dispatcher.cmd,
		}, os.Args[1:]...), os.Environ()); err != nil {
			logger.Fatalf("Error exec'ing into %s: %v", dispatcher.cmd, err)
		}
	}

	logger.Println("Falling back to authorized_keys file")
	akf, err := os.Open(authorized_keys_file)
	if err != nil {
		logger.Fatalf("Error opening authorized_keys: %v", err)
	}
	io.Copy(os.Stdout, akf)
}
