package main

import (
	"log"
	"os"
	"strings"

	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/dynamodb"
	"github.com/aws/aws-sdk-go/service/s3/s3crypto"
	"github.com/aws/aws-sdk-go/service/ses"
)

var (
	domain   = os.Getenv("DOMAIN")
	function = os.Getenv("AWS_LAMBDA_FUNCTION_NAME")

	awsSess = session.Must(session.NewSession())
	awsDDB  = dynamodb.New(awsSess)
	awsSES  = ses.New(awsSess)
	awsS3   = s3crypto.NewDecryptionClient(awsSess)
)

func main() {
	switch strings.Join(strings.Split(function, "-")[2:], "-") {
	case "web":
		webMain()
	case "forward":
		forwardMain()
	case "accounts":
		accountsMain()
	default:
		log.Println("Unknown function name:", function)
	}
}
