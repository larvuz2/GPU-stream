/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What an agent needs to drive a session: the MCP endpoint, the command that adds it to Claude,
 * and the tools it then has.
 *
 * The endpoint is the control plane's `/mcp` (streamable HTTP), authenticated with an API key's
 * secret as a bearer token. Both pages show the command from here, the landing page with
 * placeholders and the dashboard with the secret of a key just created.
 * @module
 */
import { brand } from './catalog';
import { apiUrl } from './env';

/** What the command shows where a secret belongs, safe to paste into a shell as it stands. */
export const SECRET_PLACEHOLDER = 'YOUR_API_KEY';

/** What the command shows for the control plane while none is configured. */
const HOST_PLACEHOLDER = 'https://YOUR_API_HOST';

/** A tool the MCP endpoint offers an agent. */
export interface McpTool {
  /** The tool's name, as the agent calls it. */
  name: string;
  /** What calling it does. */
  summary: string;
}

/** The tool that runs an agent's code inside the app the user is watching. */
export const SCRIPT_TOOL = 'run_blender_python';

/** The endpoint's tools, in the order an agent tends to use them. */
export const MCP_TOOLS: readonly McpTool[] = [
  { name: 'list_apps', summary: 'See which apps and tiers can be launched.' },
  { name: 'start_session', summary: 'Start a session on the tier it picks.' },
  { name: 'list_sessions', summary: 'Check what is running or queued.' },
  { name: 'get_session_link', summary: 'Hand you the link to watch the stream.' },
  { name: SCRIPT_TOOL, summary: 'Run Python inside the live Blender you are watching.' },
  { name: 'screenshot', summary: 'Look at the viewport to check its own work.' },
  { name: 'stop_session', summary: 'Shut the session down when the job is done.' },
];

/**
 * The name the MCP server is registered under in an agent, the brand in lowercase.
 *
 * @returns A name with only letters, digits, and hyphens.
 */
export function mcpServerName(): string {
  return brand
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * The address of the MCP endpoint.
 *
 * @returns The control plane's `/mcp`, under a placeholder host while none is configured.
 */
export function mcpEndpoint(): string {
  return `${apiUrl ?? HOST_PLACEHOLDER}/mcp`;
}

/**
 * The command that adds the endpoint to Claude Code.
 *
 * @param secret The API key secret to authenticate with; the placeholder when none is at hand.
 * @returns The command, ready to paste.
 */
export function mcpSetupCommand(secret: string = SECRET_PLACEHOLDER): string {
  return `claude mcp add --transport http ${mcpServerName()} ${mcpEndpoint()} --header "Authorization: Bearer ${secret}"`;
}
