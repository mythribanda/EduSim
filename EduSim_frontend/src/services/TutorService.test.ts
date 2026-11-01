import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyError,
  classifyResponseError,
  classifyNetworkOrAbortError,
  isNetworkFailure,
} from "./TutorService.ts";

test("TutorService Error Classification", async (t) => {
  const baseUrl = "http://localhost:8001";

  await t.test("TypeError from fetch produces server unreachable message", async () => {
    const error = new TypeError("Failed to fetch");
    const result = classifyNetworkOrAbortError(error, baseUrl, false);
    assert.equal(
      result,
      "Can't reach the EduSim server at http://localhost:8001. Is the backend running?",
    );

    const unifiedResult = await classifyError(error, { baseUrl });
    assert.equal(
      unifiedResult,
      "Can't reach the EduSim server at http://localhost:8001. Is the backend running?",
    );
  });

  await t.test("Network error variations identify as network failure", () => {
    assert.equal(isNetworkFailure(new TypeError("Failed to fetch")), true);
    assert.equal(isNetworkFailure(new Error("NetworkError when attempting to fetch")), true);
    assert.equal(isNetworkFailure(new Error("fetch failed")), true);
    assert.equal(isNetworkFailure(new Error("Random business logic error")), false);
  });

  await t.test("AbortError produces Request cancelled message", async () => {
    const abortErr = new DOMException("The user aborted a request.", "AbortError");
    const result = classifyNetworkOrAbortError(abortErr, baseUrl, false);
    assert.equal(result, "Request cancelled");

    const unifiedResult = await classifyError(abortErr, { baseUrl });
    assert.equal(unifiedResult, "Request cancelled");
  });

  await t.test("Timeout produces timeout explanation message", async () => {
    const timeoutErr = new DOMException("Operation timed out", "AbortError");
    const result = classifyNetworkOrAbortError(timeoutErr, baseUrl, true);
    assert.equal(
      result,
      "The AI took too long to answer. Local models can be slow on the first question; try again.",
    );

    const unifiedResult = await classifyError(timeoutErr, { baseUrl, isTimeout: true });
    assert.equal(
      unifiedResult,
      "The AI took too long to answer. Local models can be slow on the first question; try again.",
    );
  });

  await t.test("HTTP 401 response produces session expired message", async () => {
    const response = new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
    const result = await classifyResponseError(response);
    assert.equal(result, "Session expired, please log in again");

    const unifiedResult = await classifyError(response);
    assert.equal(unifiedResult, "Session expired, please log in again");
  });

  await t.test("HTTP 402 response produces OpenRouter credits message", async () => {
    const response = new Response(JSON.stringify({ message: "Payment Required" }), {
      status: 402,
      headers: { "Content-Type": "application/json" },
    });
    const result = await classifyResponseError(response);
    assert.equal(
      result,
      "OpenRouter payment required (HTTP 402). Please add credits to your OpenRouter account.",
    );

    const unifiedResult = await classifyError(response);
    assert.equal(
      unifiedResult,
      "OpenRouter payment required (HTTP 402). Please add credits to your OpenRouter account.",
    );
  });

  await t.test("HTTP 5xx response formats message and request_id", async () => {
    const response = new Response(
      JSON.stringify({
        success: false,
        message: "Internal server error",
        request_id: "req_test_abc123",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
    const result = await classifyResponseError(response);
    assert.equal(result, "Internal server error (Request ID: req_test_abc123)");

    const unifiedResult = await classifyError(response);
    assert.equal(unifiedResult, "Internal server error (Request ID: req_test_abc123)");
  });

  await t.test("HTTP 5xx response without request_id shows message", async () => {
    const response = new Response(
      JSON.stringify({
        success: false,
        message: "Database connection failed",
      }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      },
    );
    const result = await classifyResponseError(response);
    assert.equal(result, "Database connection failed");
  });

  await t.test("HTTP 4xx response shows detail if present", async () => {
    const response = new Response(
      JSON.stringify({
        detail: "Topic 'quantum-mechanics' not found in curriculum",
      }),
      {
        status: 404,
        headers: { "Content-Type": "application/json" },
      },
    );
    const result = await classifyResponseError(response);
    assert.equal(result, "Topic 'quantum-mechanics' not found in curriculum");

    const unifiedResult = await classifyError(response);
    assert.equal(unifiedResult, "Topic 'quantum-mechanics' not found in curriculum");
  });
});
