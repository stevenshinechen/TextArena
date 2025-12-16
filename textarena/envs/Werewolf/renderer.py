import json
from enum import Enum


class RenderStateFormat(Enum):
    HUMAN_READABLE = "human_readable"
    JSON = "json"
    NONE = "none"


def render_players_list(player_roles: dict, alive_players: list, show_roles: bool = False) -> str:
    """Render the player list in a clean, text-friendly format."""
    lines = []
    for pid in sorted(player_roles):
        status = "🟢 Alive" if pid in alive_players else "💀 Dead"
        lines.append(f"  • Player {pid}: {status}")
    return "\n".join(lines)


def render_alive_dead_lists(game_state: dict) -> str:
    """Render separate lists of alive and dead players for public view."""
    alive_players = game_state.get("alive_player_ids", [])
    n_players = game_state.get("num_players", 0)

    alive_sorted = sorted(alive_players)
    dead_sorted = sorted([pid for pid in range(n_players) if pid not in alive_players])

    lines = []
    lines.append("👥 Players:")

    # Alive
    lines.append("  🟢 Alive:")
    if alive_sorted:
        for pid in alive_sorted:
            lines.append(f"    • Player {pid}")
    else:
        lines.append("    • None")

    # Dead
    lines.append("  💀 Dead:")
    if dead_sorted:
        for pid in dead_sorted:
            lines.append(f"    • Player {pid}")
    else:
        lines.append("    • None")

    return "\n".join(lines)


def render_phase_info(game_state: dict) -> str:
    """Render current phase and round information."""
    phase = str(game_state.get("phase", "Unknown"))
    num_players = game_state.get("num_players", 0)
    alive_players = game_state.get("alive_player_ids", [])
    
    lines = []
    lines.append(f"🌙 Current Phase: {phase}")
    lines.append(f"👥 Alive Players: {len(alive_players)}/{num_players}")
    
    # Add phase-specific context
    if "Night" in phase or "Werewolf" in phase or "Seer" in phase or "Witch" in phase:
        lines.append("  🌃 It's night time - special roles are acting")
    elif "Day" in phase:
        lines.append("  ☀️ It's day time - all players can discuss and vote")
    
    return "\n".join(lines)


def render_night_actions(game_state: dict, viewer_is_witch: bool = False) -> str:
    """Render night phase actions and results."""
    phase = str(game_state.get("phase", "")).lower()
    if "day" in phase:
        return ""

    lines = []
    lines.append("🌙 Night Phase:")
    if viewer_is_witch:
        lines.append("  🌃 Night in progress.")
        attacked_player = game_state.get("attacked_player_id")
        if attacked_player is not None:
            lines.append(f"  ⚔️ Attack Info (Witch only): Player {attacked_player} was attacked")
    else:
        lines.append("  🌃 Night in progress. No public information is available.")
    return "\n".join(lines)


def render_day_actions(game_state: dict) -> str:
    """Render day phase actions and voting."""
    phase = str(game_state.get("phase", "")).lower()
    if "night" in phase or "werewolf" in phase or "seer" in phase or "witch" in phase:
        return ""
    
    lines = []
    lines.append("☀️ Day Actions:")
    
    # Day votes
    day_votes = game_state.get("day_votes", {})
    if day_votes:
        lines.append("  🗳️ Village Votes:")
        vote_counts = {}
        for voter, target in day_votes.items():
            vote_counts[target] = vote_counts.get(target, 0) + 1
        
        for target, count in sorted(vote_counts.items()):
            lines.append(f"    • Player {target}: {count} vote{'s' if count != 1 else ''}")
    else:
        lines.append("  🗳️ Village Votes: None yet")
    
    # Previous day results
    voted_player = game_state.get("voted_player_id")
    if voted_player is not None:
        lines.append(f"  ⚖️ Last Vote Result: Player {voted_player} was eliminated")
    
    return "\n".join(lines)


def render_game_progress(game_state: dict) -> str:
    """Render overall game progress and team composition."""
    alive_players = game_state.get("alive_player_ids", [])

    lines = []
    lines.append("📊 Game Progress:")
    lines.append(f"  👥 Players remaining: {len(alive_players)}")
    return "\n".join(lines)


def render_potion_status(game_state: dict) -> str:
    """Render Witch potion counts remaining (Witch-only)."""
    num_cures = game_state.get("num_cures", 0)
    num_poisons = game_state.get("num_poisons", 0)

    lines = []
    lines.append("🧪 Witch Potions:")
    lines.append(f"  💚 Cure potions left: {num_cures}")
    lines.append(f"  💀 Poison potions left: {num_poisons}")
    return "\n".join(lines)


def render_seer_info(game_state: dict) -> str:
    """Render Seer-only list of revealed players and their roles."""
    revealed = game_state.get("revealed_player_ids", []) or []
    player_roles = game_state.get("player_roles", {})

    lines = []
    lines.append("🔮 Seer Revelations:")
    if revealed:
        for pid in sorted(revealed):
            role = player_roles.get(pid, "Unknown")
            lines.append(f"  • Player {pid}: {role}")
    else:
        lines.append("  • No players revealed yet")
    return "\n".join(lines)


def render_guard_info(game_state: dict) -> str:
    """Render Guard-only information about last protected player."""
    protected_player_id = game_state.get("protected_player_id")
    
    lines = []
    lines.append("🛡️ Guard Protection:")
    if protected_player_id is not None:
        lines.append(f"  • Last protected: Player {protected_player_id}")
    else:
        lines.append("  • No player protected yet")
    return "\n".join(lines)


def render_human_readable_game_state(
    game_state: dict,
    viewer_is_witch: bool = False,
    viewer_is_seer: bool = False,
    viewer_is_guard: bool = False,
) -> str:
    """Render the game state in a human-readable format."""
    lines = [
        f"🐺 WEREWOLF GAME STATUS",
        "",
    ]
    
    # Core game info
    lines.append(render_phase_info(game_state))
    lines.append("")
    
    # Game progress
    lines.append(render_game_progress(game_state))
    lines.append("")
    
    # Always show alive/dead lists
    lines.append(render_alive_dead_lists(game_state))
    lines.append("")
    
    # Phase-specific actions
    night_actions = render_night_actions(game_state, viewer_is_witch=viewer_is_witch)
    if night_actions:
        lines.append(night_actions)
        lines.append("")
    
    day_actions = render_day_actions(game_state)
    if day_actions:
        lines.append(day_actions)
        lines.append("")

    # Witch-only information: potion availability
    if viewer_is_witch:
        lines.append(render_potion_status(game_state))

    # Seer-only information: revealed players and roles
    if viewer_is_seer:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(render_seer_info(game_state))
    
    # Guard-only information: last protected player
    if viewer_is_guard:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(render_guard_info(game_state))
    
    return "\n".join(lines)


def render_json_game_state(
    game_state: dict,
    viewer_is_witch: bool = False,
    viewer_is_seer: bool = False,
    viewer_is_guard: bool = False,
) -> str:
    """Render the game state in JSON format."""

    state_copy = game_state.copy()

    # Turn non-serializable objects into a serializable format
    state_copy["phase"] = str(state_copy["phase"])

    # Remove non-public information
    roles = state_copy.pop("player_roles")
    state_copy.pop("role_pids")
    state_copy.pop("poisoned_player_id")
    state_copy.pop("voted_player_id")
    state_copy.pop("werewolf_votes")
    state_copy.pop("day_votes")

    # Add werewolf ids
    werewolf_ids = [pid for pid, role in roles.items() if role == "Werewolf"]
    state_copy["werewolf_ids"] = werewolf_ids

    if state_copy["phase"] != "Phase.WITCH_CHOICE":
        # Only show attacked player during Witch phase
        state_copy.pop("attacked_player_id", None)

    if not viewer_is_witch:
        # Only show potion counts to the Witch
        state_copy.pop("num_cures", None)
        state_copy.pop("num_poisons", None)

    if not viewer_is_seer:
        # Only show revealed players to the Seer
        state_copy.pop("revealed_player_ids", None)

    return f"<gamestate>{json.dumps(state_copy, indent=None)}</gamestate>"


def render_game_state(
    game_state: dict,
    render_state_format: RenderStateFormat = RenderStateFormat.NONE,
    viewer_is_witch: bool = False,
    viewer_is_seer: bool = False,
    viewer_is_guard: bool = False,
) -> str:
    """Main Werewolf board renderer."""
    if render_state_format == RenderStateFormat.NONE:
        return ""

    if render_state_format == RenderStateFormat.HUMAN_READABLE:
        return render_human_readable_game_state(
            game_state,
            viewer_is_witch=viewer_is_witch,
            viewer_is_seer=viewer_is_seer,
            viewer_is_guard=viewer_is_guard,
        )

    if render_state_format == RenderStateFormat.JSON:
        return render_json_game_state(
            game_state,
            viewer_is_witch=viewer_is_witch,
            viewer_is_seer=viewer_is_seer,
            viewer_is_guard=viewer_is_guard,
        )
