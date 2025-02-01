.PHONY: build run

build:
	docker build -t yt-dluxe .

run: build
	docker run --rm -p 5050:5050 yt-dluxe
