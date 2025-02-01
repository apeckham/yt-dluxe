.PHONY: build run

build:
	docker build -t yt-dluxe .

run: build
	docker run --rm -p 8000:8000 yt-dluxe
