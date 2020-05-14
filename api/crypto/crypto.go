package crypto

import (
	"crypto/ed25519"
	"encoding/base64"
	"log"
	"time"

	"github.com/fernet/fernet-go"
	"github.com/vaughan0/go-ini"
)

var (
	privateKey ed25519.PrivateKey
	publicKey  ed25519.PublicKey
	fernetKey  *fernet.Key
)

func InitCrypto(config ini.File) {
	b64key, ok := config.Get("webhooks", "private-key")
	if !ok {
		log.Fatalf("No webhook key configured")
	}
	seed, err := base64.StdEncoding.DecodeString(b64key)
	if err != nil {
		log.Fatalf("base64 decode webhooks private key: %v", err)
	}
	privateKey = ed25519.NewKeyFromSeed(seed)
	publicKey, _ = privateKey.Public().(ed25519.PublicKey)

	b64fernet, ok := config.Get("sr.ht", "network-key")
	if !ok {
		log.Fatalf("No network key configured")
	}
	fernetKey, err = fernet.DecodeKey(b64fernet)
	if err != nil {
		log.Fatalf("Load Fernet network encryption key: %v", err)
	}
}

func Sign(payload []byte) []byte {
	return ed25519.Sign(privateKey, payload)
}

func Verify(payload, signature []byte) bool {
	return ed25519.Verify(publicKey, payload, signature)
}

func Encrypt(payload []byte) []byte {
	msg, err := fernet.EncryptAndSign(payload, fernetKey)
	if err != nil {
		log.Fatalf("Error encrypting payload: %v", err)
	}
	return msg
}

func Decrypt(payload []byte) []byte {
	return fernet.VerifyAndDecrypt(payload,
		time.Duration(0), []*fernet.Key{fernetKey})
}
