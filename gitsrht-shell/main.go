package main

import (
	"bytes"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	gopath "path"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"

	"github.com/google/shlex"
	"github.com/vaughan0/go-ini"
	"golang.org/x/crypto/ed25519"
)

func main() {
	var (
		config ini.File
		err    error
		logger *log.Logger

		userId   int
		username string

		origin   string
		repos    string
		privkey  ed25519.PrivateKey

		cmdstr   string
		cmd      []string
	)

	logf, err := os.OpenFile("/var/log/gitsrht-shell",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Warning: unable to open log file: %v " +
			"(using stderr instead)", err)
		logger = log.New(os.Stderr, "", log.LstdFlags)
	} else {
		logger = log.New(logf, "", log.LstdFlags)
	}

	if len(os.Args) < 2 {
		logger.Fatalf("Expected two arguments from SSH")
	}
	logger.Printf("os.Args: %v", os.Args)

	if userId, err = strconv.Atoi(os.Args[1]); err != nil {
		logger.Fatalf("Couldn't interpret user ID: %v", err)
	}
	username = os.Args[2]

	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		logger.Fatalf("Failed to load config file: %v", err)
	}

	origin, ok := config.Get("git.sr.ht", "internal-origin")
	if !ok {
		origin, ok = config.Get("git.sr.ht", "origin")
	}
	if !ok || origin == "" {
		logger.Fatalf("No origin configured for git.sr.ht")
	}

	repos, ok = config.Get("git.sr.ht", "repos")
	if !ok {
		logger.Fatalf("No repo path configured for git.sr.ht")
	}

	b64key, ok := config.Get("webhooks", "private-key")
	if !ok {
		logger.Fatalf("No webhook key configured")
	}
	seed, err := base64.StdEncoding.DecodeString(b64key)
	if err != nil {
		logger.Fatalf("base64 decode webhooks private key: %v", err)
	}
	privkey = ed25519.NewKeyFromSeed(seed)

	cmdstr, ok = os.LookupEnv("SSH_ORIGINAL_COMMAND")
	if !ok {
		cmdstr = ""
	}

	cmd, err = shlex.Split(cmdstr)
	if err != nil {
		logger.Fatalf("Unable to parse command: %v", err)
	}

	logger.Println("Running git.sr.ht shell")

	validCommands := []string{
		"git-receive-pack", "git-upload-pack", "git-upload-archive",
	}
	var valid bool
	for _, c := range validCommands {
		if len(cmd) > 0 && c == cmd[0] {
			valid = true
		}
	}

	if !valid {
		logger.Printf("Not permitting unacceptable command: %v", cmd)
		fmt.Printf("Hi %s! You've successfully authenticated, " +
			"but I do not provide an interactive shell. Bye!\n", username)
		os.Exit(128)
	}

	os.Chdir(repos)

	path := cmd[len(cmd)-1]
	path, err = filepath.Abs(path)
	if err != nil {
		logger.Fatalf("filepath.Abs(%s): %v", path, err)
	}
	if !strings.HasPrefix(path, repos) {
		path = gopath.Join(repos, path)
	}
	cmd[len(cmd)-1] = path

	access := 1
	if cmd[0] == "git-receive-pack" {
		access = 2
	}

	payload, err := json.Marshal(struct {
		Access int    `json:"access"`
		Path   string `json:"path"`
		UserId int    `json:"user_id"`
	}{
		Access: access,
		Path:   path,
		UserId: userId,
	})
	if err != nil {
		logger.Fatalf("json.Marshal: %v", err)
	}
	logger.Println(string(payload))

	var (
		nonceSeed []byte
		nonceHex  []byte
	)
	_, err = rand.Read(nonceSeed)
	if err != nil {
		logger.Fatalf("generate nonce: %v", err)
	}
	hex.Encode(nonceHex, nonceSeed)
	signature := ed25519.Sign(privkey, append(payload, nonceHex...))

	headers := make(http.Header)
	headers.Add("Content-Type", "application/json")
	headers.Add("X-Payload-Nonce", string(nonceHex))
	headers.Add("X-Payload-Signature",
		base64.StdEncoding.EncodeToString(signature))

	check, err := url.Parse(fmt.Sprintf("%s/internal/push-check", origin))
	if err != nil {
		logger.Fatalf("url.Parse: %v", err)
	}
	req := http.Request{
		Body:          ioutil.NopCloser(bytes.NewBuffer(payload)),
		ContentLength: int64(len(payload)),
		Header:        headers,
		Method:        "POST",
		URL:           check,
	}
	resp, err := http.DefaultClient.Do(&req)
	if err != nil {
		logger.Fatalf("http.Client.Do: %v", err)
	}
	defer resp.Body.Close()
	results, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		logger.Fatal("ReadAll(resp.Body): %v", err)
	}
	logger.Println(string(results))

	switch resp.StatusCode {
	case 302:
		var redirect struct {
			Redirect string `json:"redirect"`
		}
		json.Unmarshal(results, &redirect)

		fmt.Printf("\n\t\033[93mNOTICE\033[0m\n\n")
		fmt.Printf("\tThis repository has moved:\n\n")
		fmt.Printf("\t%s\n\n", redirect.Redirect)
		fmt.Printf("\tPlease update your remote.\n\n\n")
		os.Exit(128)
	case 200:
		logger.Printf("Executing command: %v", cmd)
		bin, err := exec.LookPath(cmd[0])
		if err != nil {
			logger.Fatalf("exec.LookPath: %v", err)
		}
		if err := syscall.Exec(bin, cmd,
			append(os.Environ(), fmt.Sprintf(
				"SRHT_PUSH_CTX=%s", string(results)))); err != nil {
					logger.Fatalf("syscall.Exec: %v", err)
		}
	default:
		var why struct {
			Why string `json:"why"`
		}
		json.Unmarshal(results, &why)
		fmt.Println(why.Why)
		os.Exit(128)
	}
}
