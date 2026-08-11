.PHONY: verify test status

verify:
	./scripts/agent-verify.sh

test:
	python3 -m unittest discover -s tests -v

status:
	./bin/learn status
