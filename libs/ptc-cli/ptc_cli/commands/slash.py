"""Slash command handlers for the CLI (API mode)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ptc_cli.core import console
from ptc_cli.display import show_help
from ptc_cli.streaming.executor import reconnect_to_workflow, replay_conversation


async def _select_or_create_workspace_interactive(
    client: "SSEStreamClient",
) -> str | None:
    """Select an existing workspace or create a new one."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    workspaces = await client.list_workspaces()

    options: list[tuple[str, dict[str, Any]]] = [("Create a new workspace", {"action": "create"})]
    for ws in workspaces:
        workspace_id = str(ws.get("workspace_id", ""))
        name = str(ws.get("name", "(unnamed)"))
        status = str(ws.get("status", ""))
        options.append(
            (
                f"Use existing: {name} ({workspace_id[:12]}) [{status}]",
                {"action": "use", "workspace_id": workspace_id},
            )
        )

    selected = [0]

    def menu_text() -> str:
        lines = ["Select a workspace (Up/Down, Enter):", ""]
        for idx, (label, _meta) in enumerate(options):
            prefix = ">" if idx == selected[0] else " "
            lines.append(f" {prefix} {idx+1}. {label}")
        lines.append("")
        lines.append("(Ctrl+C to cancel)")
        return "\n".join(lines)

    kb = KeyBindings()

    @kb.add("up")
    def _(_event: Any) -> None:
        selected[0] = max(0, selected[0] - 1)

    @kb.add("down")
    def _(_event: Any) -> None:
        selected[0] = min(len(options) - 1, selected[0] + 1)

    @kb.add("enter")
    def _(event: Any) -> None:
        event.app.exit(result=selected[0])

    @kb.add("c-c")
    def _(event: Any) -> None:
        event.app.exit(result=-1)

    app: Application[int] = Application(
        layout=Layout(Window(FormattedTextControl(menu_text))),
        key_bindings=kb,
        full_screen=False,
    )

    choice = await app.run_async()
    if choice == -1:
        return None

    picked = options[choice][1]
    if picked.get("action") == "use":
        return str(picked.get("workspace_id"))

    name_default = f"cli-{time.strftime('%Y%m%d-%H%M%S')}"
    name = console.input(f"Workspace name [dim]({name_default})[/dim]: ").strip() or name_default
    console.print("[dim]Creating workspace (can take ~60s)...[/dim]")
    ws = await client.create_workspace(name=name)
    return ws.get("workspace_id")


async def _ensure_workspace_running(client: "SSEStreamClient", workspace_id: str) -> bool:
    try:
        workspace = await client.get_workspace(workspace_id)
        if not workspace:
            return False
        if workspace.get("status") != "running":
            await client.start_workspace(workspace_id)
        return True
    except Exception:
        return False


if TYPE_CHECKING:
    from ptc_cli.api.client import SSEStreamClient
    from ptc_cli.core.state import SessionState
    from ptc_cli.display.tokens import TokenTracker


async def handle_command(
    command: str,
    client: SSEStreamClient,
    token_tracker: TokenTracker,
    session_state: SessionState,
) -> str | None:
    """Handle slash commands.

    Args:
        command: The command string (e.g., "/help")
        client: SSE stream client for API communication
        token_tracker: Token tracker for usage display
        session_state: Session state for conversation management

    Returns:
        "exit" if should exit, "handled" if command was processed, None otherwise
    """
    cmd = command.strip()
    cmd_lower = cmd.lower()

    # Exit command
    if cmd_lower in ("/exit", "/q"):
        return "exit"

    if cmd_lower == "/help":
        show_help()

    elif cmd_lower in ("/new", "/clear"):
        if cmd_lower == "/clear":
            console.print("[dim]/clear is deprecated; use /new[/dim]")

        # Ensure we have a workspace first (workspace_id is required for chat)
        if not client.workspace_id:
            console.print()
            console.print("[yellow]No workspace selected.[/yellow]")

            workspace_id = await _select_or_create_workspace_interactive(client)
            if not workspace_id:
                console.print("[dim]Cancelled[/dim]")
                console.print()
                return "handled"

            client.workspace_id = workspace_id

            if not await _ensure_workspace_running(client, client.workspace_id):
                console.print(f"[red]Workspace not available: {client.workspace_id}[/red]")
                console.print()
                return "handled"

        # Start a fresh conversation thread
        session_state.reset_thread()
        client.thread_id = session_state.thread_id
        console.print("[green]Started new conversation.[/green]")
        console.print(f"[dim]Thread: {client.thread_id}[/dim]")
        console.print(f"[dim]Workspace: {client.workspace_id}[/dim]")
        console.print()

    elif cmd_lower == "/tokens":
        token_tracker.display()

    elif cmd_lower == "/model" or cmd_lower.startswith("/model "):
        from ptc_cli.input import select_model_interactive

        console.print()
        if cmd_lower == "/model":
            # Show interactive model selection
            current_model = getattr(session_state, "llm_model", None)
            selected = await select_model_interactive(current_model)
            if selected:
                session_state.llm_model = selected
                console.print(f"[green]Model set to:[/green] {selected}")
            else:
                console.print("[dim]Model selection cancelled[/dim]")
        else:
            # Direct model name input
            model_name = cmd[7:].strip()
            if model_name:
                session_state.llm_model = model_name
                console.print(f"[green]Model set to:[/green] {model_name}")
            else:
                console.print("[yellow]Please specify a model name[/yellow]")
        console.print()

    elif cmd_lower in ("/files", "/view", "/copy", "/download") or cmd_lower.startswith(
        ("/files ", "/view ", "/copy ", "/download ")
    ):
        console.print()
        console.print("[yellow]Sandbox commands are not available via API.[/yellow]")
        console.print("[dim]File operations are handled through the agent.[/dim]")
        console.print()

    elif cmd_lower == "/status":
        console.print()

        # Show workflow status if thread_id exists
        if client.thread_id:
            try:
                status = await client.get_workflow_status(client.thread_id)
                console.print(f"[cyan]Thread:[/cyan] {client.thread_id}")
                console.print(f"[cyan]Workflow Status:[/cyan] {status.get('status', 'unknown')}")

                # Show background task info
                active_subagents = status.get("active_subagents", [])
                completed_subagents = status.get("completed_subagents", [])

                if active_subagents:
                    console.print(f"[cyan]Running:[/cyan]")
                    for task in active_subagents:
                        console.print(f"  - {task}")

                if completed_subagents:
                    console.print(f"[cyan]Completed:[/cyan]")
                    for task in completed_subagents:
                        console.print(f"  - {task}")

                if status.get("soft_interrupted"):
                    console.print("[yellow]Workflow was soft-interrupted (subagents may still be running)[/yellow]")

            except Exception as e:
                console.print(f"[dim]Thread: {client.thread_id}[/dim]")
                console.print(f"[dim]Could not get workflow status: {e}[/dim]")
        else:
            console.print("[dim]No active workflow thread[/dim]")

        console.print()

        # Show workspace status if workspace_id exists
        if client.workspace_id:
            try:
                workspace = await client.get_workspace(client.workspace_id)
                if workspace:
                    console.print(f"[cyan]Workspace:[/cyan] {workspace.get('name', 'N/A')}")
                    console.print(f"[cyan]Workspace ID:[/cyan] {workspace.get('workspace_id', 'N/A')}")
                    console.print(f"[cyan]Workspace Status:[/cyan] {workspace.get('status', 'N/A')}")
                else:
                    console.print("[dim]Workspace not found[/dim]")
            except Exception as e:
                console.print(f"[dim]Could not get workspace status: {e}[/dim]")

        console.print(f"[cyan]Server:[/cyan] {client.base_url}")
        console.print()

    elif cmd_lower.startswith("/workspace") or cmd_lower == "/workspaces":
        parts = cmd_lower.split()

        # Shortcut: /workspace stop (stop current workspace)
        if len(parts) >= 2 and parts[1] == "stop":
            if not client.workspace_id:
                console.print("[yellow]No active workspace[/yellow]")
                console.print()
                return "handled"
            try:
                await client.stop_workspace(client.workspace_id)
                console.print(f"[green]Workspace stopped:[/green] {client.workspace_id}")
                console.print()
            except Exception as e:
                console.print(f"[yellow]Could not stop workspace: {e}[/yellow]")
                console.print()
            return "handled"

        # Interactive workspace picker
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        console.print()

        workspaces: list[dict[str, Any]] = await client.list_workspaces()
        if not workspaces:
            console.print("[yellow]No workspaces found[/yellow]")
            console.print("[dim]Use /new to create one.[/dim]")
            console.print()
            return "handled"

        selected = [0]
        status_line = ["Enter = switch | s = start | x = stop | n = new | Ctrl+C = cancel"]

        def menu_text() -> str:
            lines = ["Workspaces:", status_line[0], ""]
            for idx, ws in enumerate(workspaces):
                workspace_id = str(ws.get("workspace_id", ""))
                name = str(ws.get("name", "(unnamed)"))
                status = str(ws.get("status", ""))
                prefix = ">" if idx == selected[0] else " "
                active = " *" if client.workspace_id == workspace_id else ""
                lines.append(
                    f" {prefix} {idx+1}. {name} ({workspace_id[:12]}) [{status}]{active}"
                )
            return "\n".join(lines)

        kb = KeyBindings()

        @kb.add("up")
        def _(_event: Any) -> None:
            selected[0] = max(0, selected[0] - 1)

        @kb.add("down")
        def _(_event: Any) -> None:
            selected[0] = min(len(workspaces) - 1, selected[0] + 1)

        @kb.add("enter")
        def _(event: Any) -> None:
            event.app.exit(result=("switch", selected[0]))

        @kb.add("s")
        def _(event: Any) -> None:
            event.app.exit(result=("start", selected[0]))

        @kb.add("x")
        def _(event: Any) -> None:
            event.app.exit(result=("stop", selected[0]))

        @kb.add("n")
        def _(event: Any) -> None:
            event.app.exit(result=("new", -1))

        @kb.add("c-c")
        def _(event: Any) -> None:
            event.app.exit(result=("cancel", -1))

        workspace_app: Application[tuple[str, int]] = Application(
            layout=Layout(Window(FormattedTextControl(menu_text))),
            key_bindings=kb,
            full_screen=False,
        )

        action, index = await workspace_app.run_async()
        if action == "cancel":
            console.print("[dim]Cancelled[/dim]")
            console.print()
            return "handled"

        if action == "new":
            workspace_id = await _select_or_create_workspace_interactive(client)
            if not workspace_id:
                console.print("[dim]Cancelled[/dim]")
                console.print()
                return "handled"
            client.workspace_id = workspace_id
            await _ensure_workspace_running(client, client.workspace_id)
            session_state.reset_thread()
            client.thread_id = session_state.thread_id
            console.print("[green]Switched to new workspace[/green]")
            console.print(f"[dim]Workspace: {client.workspace_id}[/dim]")
            console.print(f"[dim]Thread: {client.thread_id}[/dim]")
            console.print()
            return "handled"

        if index < 0 or index >= len(workspaces):
            console.print("[red]Invalid selection[/red]")
            console.print()
            return "handled"

        chosen = workspaces[index]
        workspace_id = str(chosen.get("workspace_id", ""))
        if not workspace_id:
            console.print("[red]Invalid workspace selection[/red]")
            console.print()
            return "handled"

        if action == "start":
            try:
                await client.start_workspace(workspace_id)
                console.print(f"[green]Workspace started:[/green] {workspace_id}")
            except Exception as e:
                console.print(f"[yellow]Could not start workspace: {e}[/yellow]")
            console.print()
            return "handled"

        if action == "stop":
            try:
                await client.stop_workspace(workspace_id)
                console.print(f"[green]Workspace stopped:[/green] {workspace_id}")
            except Exception as e:
                console.print(f"[yellow]Could not stop workspace: {e}[/yellow]")
            console.print()
            return "handled"

        # switch
        client.workspace_id = workspace_id
        await _ensure_workspace_running(client, client.workspace_id)
        session_state.reset_thread()
        client.thread_id = session_state.thread_id

        console.print("[green]Switched workspace.[/green]")
        console.print(f"[dim]Workspace: {client.workspace_id}[/dim]")
        console.print(f"[dim]Thread reset: {client.thread_id}[/dim]")
        console.print()
        return "handled"

    elif cmd_lower == "/cancel":
        # Cancel running workflow
        if client.thread_id:
            try:
                await client.cancel_workflow(client.thread_id)
                console.print("[green]Workflow cancelled[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not cancel workflow: {e}[/yellow]")
        else:
            console.print("[yellow]No active workflow to cancel[/yellow]")

    elif cmd_lower == "/conversation":
        # List and open past conversations for this user
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        console.print()
        data = await client.list_conversations(limit=50)
        threads = data.get("threads", []) or []
        if not threads:
            console.print("[yellow]No conversations found[/yellow]")
            console.print()
            return "handled"

        selected = [0]

        def menu_text() -> str:
            lines = ["Select a conversation (Up/Down, Enter):", ""]
            for idx, item in enumerate(threads):
                thread_id = str(item.get("thread_id", ""))
                workspace_id = str(item.get("workspace_id", ""))
                status = str(item.get("current_status", ""))
                first_query = str(item.get("first_query_content") or "")
                if len(first_query) > 60:
                    first_query = first_query[:57] + "..."
                prefix = ">" if idx == selected[0] else " "
                preview = f" - {first_query}" if first_query else ""
                lines.append(
                    f" {prefix} {idx+1}. {thread_id[:12]}  ws={workspace_id[:12]}  {status}{preview}"
                )
            lines.append("")
            lines.append("(Ctrl+C to cancel)")
            return "\n".join(lines)

        kb = KeyBindings()

        @kb.add("up")
        def _(_event: object) -> None:
            selected[0] = max(0, selected[0] - 1)

        @kb.add("down")
        def _(_event: object) -> None:
            selected[0] = min(len(threads) - 1, selected[0] + 1)

        @kb.add("enter")
        def _(event: Any) -> None:
            event.app.exit(result=selected[0])

        @kb.add("c-c")
        def _(event: Any) -> None:
            event.app.exit(result=-1)

        app: Application[int] = Application(
            layout=Layout(Window(FormattedTextControl(menu_text))),
            key_bindings=kb,
            full_screen=False,
        )

        choice = await app.run_async()
        if choice == -1:
            console.print("[dim]Cancelled[/dim]")
            console.print()
            return "handled"

        chosen = threads[choice]
        thread_id = str(chosen.get("thread_id"))
        workspace_id = str(chosen.get("workspace_id"))

        if not thread_id or not workspace_id:
            console.print("[red]Invalid conversation selection[/red]")
            console.print()
            return "handled"

        # Switch active thread/workspace
        session_state.thread_id = thread_id
        client.thread_id = thread_id
        client.workspace_id = workspace_id

        try:
            ws = await client.get_workspace(workspace_id)
            if not ws:
                console.print(f"[red]Workspace not found: {workspace_id}[/red]")
                console.print()
                return "handled"
            if ws.get("status") != "running":
                await client.start_workspace(workspace_id)
        except Exception as e:
            console.print(f"[yellow]Could not start workspace: {e}[/yellow]")
            console.print()

        await replay_conversation(client, session_state)
        return "handled"

    elif cmd_lower == "/reconnect":
        # Reconnect to running workflow (useful after ESC interrupt)
        from ptc_cli.core.state import ReconnectStateManager

        state_manager = ReconnectStateManager()

        if session_state.thread_id:
            # Load last_event_id from saved state
            saved_state = state_manager.load_state(session_state.thread_id)
            if saved_state:
                client.last_event_id = saved_state.get("last_event_id", 0)
            await reconnect_to_workflow(client, session_state, token_tracker)
        else:
            # Try to load latest session
            latest_thread = state_manager.get_latest_thread_id()
            if latest_thread:
                session_state.thread_id = latest_thread
                client.thread_id = latest_thread
                saved_state = state_manager.load_state(latest_thread)
                if saved_state:
                    client.last_event_id = saved_state.get("last_event_id", 0)
                console.print(f"[dim]Loaded session: {latest_thread[:16]}...[/dim]")
                await reconnect_to_workflow(client, session_state, token_tracker)
            else:
                console.print("[yellow]No workflow sessions to reconnect to[/yellow]")
                console.print("[dim]Start a task first, then use ESC to soft-interrupt.[/dim]")

    else:
        # Unknown command
        console.print(f"[yellow]Unknown command: {command}[/yellow]")
        console.print(
            "[dim]Available: /help, /new, /workspace, /conversation, /tokens, /model, /status, /cancel, /reconnect, /exit[/dim]"
        )

    return "handled"
