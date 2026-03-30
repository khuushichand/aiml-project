import React from "react"
import type { NetworkingIssue } from "@web/lib/api-base"

type ConfigurationErrorScreenProps = {
  issue: NetworkingIssue
}

export const ConfigurationErrorScreen = ({
  issue
}: ConfigurationErrorScreenProps) => {
  if (issue.kind === "loopback_api_not_browser_reachable") {
    return (
      <main
        data-testid="networking-config-error"
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: "2rem",
          background: "#f7f4ee",
          color: "#1f1a17"
        }}>
        <section
          style={{
            width: "100%",
            maxWidth: "40rem",
            padding: "2rem",
            borderRadius: "1rem",
            border: "1px solid #d8cdc1",
            background: "#fffaf4",
            boxShadow: "0 20px 50px rgba(61, 42, 27, 0.08)"
          }}>
          <h1 style={{ marginTop: 0 }}>WebUI networking configuration error</h1>
          <p>
            The configured API URL points to <code>{issue.apiOrigin}</code>,
            which is only reachable from the host machine.
          </p>
          <p>
            This page is running from <code>{issue.pageOrigin}</code>, so
            browsers on other devices cannot connect to that loopback API
            address.
          </p>
          <p style={{ marginBottom: 0 }}>
            Set the WebUI API URL to a LAN-reachable address for the API host,
            or switch to quickstart mode so the browser uses the same-origin
            proxy instead.
          </p>
        </section>
      </main>
    )
  }

  return null
}
