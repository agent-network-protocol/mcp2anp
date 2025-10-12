# Makefile to manage mcp2anp servers via nohup
# Targets:
#   start         -> start both server_http and server_remote
#   stop          -> stop both server_http and server_remote
#   start-http    -> start FastAPI HTTP server (port 9881)
#   stop-http     -> stop FastAPI HTTP server
#   start-remote  -> start remote MCP server (port 9880)
#   stop-remote   -> stop remote MCP server

SHELL := /bin/bash

UV := uv
PYTHON := python

# HTTP server (FastAPI)
HTTP_HOST := 0.0.0.0
HTTP_PORT := 9881

# Remote MCP server (fastmcp)
REMOTE_HOST := 0.0.0.0
REMOTE_PORT := 9880

PID_DIR := $(CURDIR)/.pids
LOG_DIR := $(CURDIR)/logs

HTTP_PID := $(PID_DIR)/server_http.pid
REMOTE_PID := $(PID_DIR)/server_remote.pid

HTTP_LOG := $(LOG_DIR)/server_http.log
REMOTE_LOG := $(LOG_DIR)/server_remote.log

.PHONY: start stop start-http stop-http start-remote stop-remote status clean-logs

start: start-http start-remote

stop: stop-http stop-remote

status:
	@echo "server_http:"
	@if [ -f $(HTTP_PID) ] && kill -0 $$(cat $(HTTP_PID)) 2>/dev/null; then \
		echo "  running (PID $$(cat $(HTTP_PID)))"; \
	else \
		echo "  not running"; \
	fi
	@echo "server_remote:"
	@if [ -f $(REMOTE_PID) ] && kill -0 $$(cat $(REMOTE_PID)) 2>/dev/null; then \
		echo "  running (PID $$(cat $(REMOTE_PID)))"; \
	else \
		echo "  not running"; \
	fi

start-http:
	@mkdir -p $(PID_DIR) $(LOG_DIR)
	@if [ -f $(HTTP_PID) ] && kill -0 $$(cat $(HTTP_PID)) 2>/dev/null; then \
		echo "server_http already running (PID $$(cat $(HTTP_PID)))"; \
	else \
		echo "Starting server_http on $(HTTP_HOST):$(HTTP_PORT)..."; \
		( nohup $(UV) run $(PYTHON) -m mcp2anp.server_http --host $(HTTP_HOST) --port $(HTTP_PORT) >> $(HTTP_LOG) 2>&1 & echo $$! > $(HTTP_PID) ); \
		sleep 0.3; \
		if kill -0 $$(cat $(HTTP_PID)) 2>/dev/null; then \
			echo "server_http started (PID $$(cat $(HTTP_PID))), logs: $(HTTP_LOG)"; \
		else \
			echo "server_http failed to start; see logs: $(HTTP_LOG)"; \
			rm -f $(HTTP_PID); \
			exit 1; \
		fi; \
	fi

stop-http:
	@if [ -f $(HTTP_PID) ]; then \
		PID=$$(cat $(HTTP_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping server_http (PID $$PID)..."; \
			kill $$PID; \
			for i in $$(seq 1 20); do \
				if kill -0 $$PID 2>/dev/null; then sleep 0.2; else break; fi; \
			done; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Force killing server_http (PID $$PID)"; \
				kill -9 $$PID; \
			fi; \
		fi; \
		rm -f $(HTTP_PID); \
		echo "server_http stopped"; \
	else \
		echo "server_http not running (no pidfile)"; \
	fi

start-remote:
	@mkdir -p $(PID_DIR) $(LOG_DIR)
	@if [ -f $(REMOTE_PID) ] && kill -0 $$(cat $(REMOTE_PID)) 2>/dev/null; then \
		echo "server_remote already running (PID $$(cat $(REMOTE_PID)))"; \
	else \
		echo "Starting server_remote on $(REMOTE_HOST):$(REMOTE_PORT)..."; \
		( nohup $(UV) run $(PYTHON) -m mcp2anp.server_remote --host $(REMOTE_HOST) --port $(REMOTE_PORT) >> $(REMOTE_LOG) 2>&1 & echo $$! > $(REMOTE_PID) ); \
		sleep 0.3; \
		if kill -0 $$(cat $(REMOTE_PID)) 2>/dev/null; then \
			echo "server_remote started (PID $$(cat $(REMOTE_PID))), logs: $(REMOTE_LOG)"; \
		else \
			echo "server_remote failed to start; see logs: $(REMOTE_LOG)"; \
			rm -f $(REMOTE_PID); \
			exit 1; \
		fi; \
	fi

stop-remote:
	@if [ -f $(REMOTE_PID) ]; then \
		PID=$$(cat $(REMOTE_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping server_remote (PID $$PID)..."; \
			kill $$PID; \
			for i in $$(seq 1 20); do \
				if kill -0 $$PID 2>/dev/null; then sleep 0.2; else break; fi; \
			done; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Force killing server_remote (PID $$PID)"; \
				kill -9 $$PID; \
			fi; \
		fi; \
		rm -f $(REMOTE_PID); \
		echo "server_remote stopped"; \
	else \
		echo "server_remote not running (no pidfile)"; \
	fi

clean-logs:
	rm -f $(HTTP_LOG) $(REMOTE_LOG)


