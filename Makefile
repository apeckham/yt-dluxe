.PHONY: build run

build:
	docker build -t yt-dluxe .

run: build
	docker run --rm -p 5051:5051 yt-dluxe
