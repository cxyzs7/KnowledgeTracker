import logging
import git

logger = logging.getLogger(__name__)


class GitSyncError(Exception):
    pass


def sync_vault(vault_path: str, commit_message: str) -> None:
    """Pull latest, stage all, commit if changed, push. Local runs only."""
    try:
        repo = git.Repo(vault_path)
        repo.git.add(A=True)
        if repo.is_dirty(index=True):
            repo.index.commit(commit_message)
        repo.remotes.origin.pull(rebase=True)
        repo.remotes.origin.push()
        logger.info("Vault synced: %s", commit_message)
    except git.GitCommandError as e:
        raise GitSyncError(f"Git sync failed: {e}") from e
