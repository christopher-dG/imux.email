build:
	go build -ldflags="-s -w"
	rm -f imux.zip
	zip -r imux.zip imux templates

test:
	go test -v -cover
