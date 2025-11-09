"""
Database backup and restore utilities for Daedelus.

Provides automated backup creation, restoration, and management.

Created by: orpheus497
"""

import gzip
import logging
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages database backups with compression and rotation.

    Features:
    - Automatic backup creation
    - Gzip compression
    - Backup rotation (keep N most recent)
    - Restoration from backups
    - Backup verification
    """

    def __init__(
        self,
        source_db: Path,
        backup_dir: Path | None = None,
        max_backups: int = 5,
    ) -> None:
        """
        Initialize backup manager.

        Args:
            source_db: Path to source database file
            backup_dir: Directory for backups (default: source_db.parent / 'backups')
            max_backups: Maximum number of backups to keep
        """
        self.source_db = Path(source_db).expanduser()
        self.backup_dir = (
            Path(backup_dir).expanduser() if backup_dir else self.source_db.parent / "backups"
        )
        self.max_backups = max_backups

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Backup manager initialized: {self.backup_dir}")

    def create_backup(self, compress: bool = True, note: str | None = None) -> Path:
        """
        Create a backup of the database.

        Args:
            compress: Whether to compress with gzip
            note: Optional note to include in filename

        Returns:
            Path to created backup file

        Raises:
            FileNotFoundError: If source database doesn't exist
            IOError: If backup creation fails
        """
        if not self.source_db.exists():
            raise FileNotFoundError(f"Source database not found: {self.source_db}")

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        note_part = f"_{note}" if note else ""
        ext = ".gz" if compress else ""

        backup_name = f"daedelus_backup_{timestamp}{note_part}.db{ext}"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Creating backup: {backup_name}")

        try:
            if compress:
                # Compressed backup
                with open(self.source_db, "rb") as f_in:
                    with gzip.open(backup_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Uncompressed backup
                shutil.copy2(self.source_db, backup_path)

            # Get sizes
            source_size = self.source_db.stat().st_size
            backup_size = backup_path.stat().st_size
            ratio = (1 - backup_size / source_size) * 100 if compress else 0

            logger.info(f"✓ Backup created: {backup_path}")
            logger.info(f"  Source size: {source_size / 1024:.2f} KB")
            logger.info(f"  Backup size: {backup_size / 1024:.2f} KB")
            if compress:
                logger.info(f"  Compression: {ratio:.1f}%")

            # Cleanup old backups
            self.cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            if backup_path.exists():
                backup_path.unlink()
            raise OSError(f"Failed to create backup: {e}") from e

    def restore_backup(self, backup_path: Path, create_backup_first: bool = True) -> None:
        """
        Restore database from a backup.

        Args:
            backup_path: Path to backup file
            create_backup_first: Whether to backup current DB before restoring

        Raises:
            FileNotFoundError: If backup file doesn't exist
            IOError: If restoration fails
        """
        backup_path = Path(backup_path).expanduser()

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        logger.info(f"Restoring from backup: {backup_path.name}")

        # Backup current database first
        if create_backup_first and self.source_db.exists():
            logger.info("Creating safety backup of current database...")
            self.create_backup(note="pre_restore")

        try:
            # Determine if backup is compressed
            is_compressed = backup_path.suffix == ".gz"

            if is_compressed:
                # Decompress and restore
                with gzip.open(backup_path, "rb") as f_in:
                    with open(self.source_db, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Direct copy
                shutil.copy2(backup_path, self.source_db)

            logger.info(f"✓ Database restored from {backup_path.name}")

        except Exception as e:
            logger.error(f"Restoration failed: {e}")
            raise OSError(f"Failed to restore backup: {e}") from e

    def list_backups(self) -> list[dict]:
        """
        List all available backups.

        Returns:
            List of backup info dictionaries
        """
        backups = []

        for backup_file in sorted(self.backup_dir.glob("daedelus_backup_*.db*")):
            # Parse timestamp from filename
            try:
                # Extract timestamp (format: daedelus_backup_20250109_143022.db.gz)
                # Use regex for more robust parsing
                match = re.search(r"daedelus_backup_(\d{8})_(\d{6})", backup_file.name)
                if match:
                    date_str = match.group(1)
                    time_str = match.group(2)
                    timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                else:
                    # Fallback to file modification time if filename doesn't match pattern
                    logger.warning(
                        f"Backup filename doesn't match expected format: {backup_file.name}"
                    )
                    timestamp = datetime.fromtimestamp(backup_file.stat().st_mtime)

                backups.append(
                    {
                        "path": backup_file,
                        "name": backup_file.name,
                        "timestamp": timestamp,
                        "size_bytes": backup_file.stat().st_size,
                        "compressed": backup_file.suffix == ".gz",
                    }
                )

            except Exception as e:
                logger.warning(f"Failed to parse backup {backup_file.name}: {e}")

        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

    def cleanup_old_backups(self) -> int:
        """
        Remove old backups beyond max_backups limit.

        Returns:
            Number of backups deleted
        """
        backups = self.list_backups()

        if len(backups) <= self.max_backups:
            return 0

        # Delete oldest backups
        to_delete = backups[self.max_backups :]
        deleted_count = 0

        for backup in to_delete:
            try:
                backup["path"].unlink()
                logger.info(f"Deleted old backup: {backup['name']}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {backup['name']}: {e}")

        if deleted_count > 0:
            logger.info(f"✓ Cleaned up {deleted_count} old backups")

        return deleted_count

    def verify_backup(self, backup_path: Path) -> bool:
        """
        Verify a backup file integrity.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid, False otherwise
        """
        backup_path = Path(backup_path).expanduser()

        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        is_compressed = backup_path.suffix == ".gz"

        try:
            if is_compressed:
                # Try to read compressed file
                with gzip.open(backup_path, "rb") as f:
                    # Read first few bytes to verify
                    data = f.read(16)
                    if not data:
                        logger.error("Backup file is empty")
                        return False
            else:
                # Try to read uncompressed file
                with open(backup_path, "rb") as f:
                    data = f.read(16)
                    if not data:
                        logger.error("Backup file is empty")
                        return False

            logger.info(f"✓ Backup file is valid: {backup_path.name}")
            return True

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    def get_latest_backup(self) -> Path | None:
        """
        Get the most recent backup.

        Returns:
            Path to latest backup, or None if no backups exist
        """
        backups = self.list_backups()
        if not backups:
            return None
        return backups[0]["path"]

    def auto_backup(self, interval_hours: int = 24) -> Path | None:
        """
        Create automatic backup if needed based on interval.

        Args:
            interval_hours: Hours between automatic backups

        Returns:
            Path to created backup, or None if backup not needed
        """
        latest = self.get_latest_backup()

        # Create backup if no backups exist
        if not latest:
            logger.info("No existing backups, creating first backup")
            return self.create_backup(note="auto")

        # Check if backup is needed
        backups = self.list_backups()
        latest_time = backups[0]["timestamp"]
        age = datetime.now() - latest_time

        if age > timedelta(hours=interval_hours):
            logger.info(
                f"Last backup is {age.total_seconds() / 3600:.1f}h old, creating new backup"
            )
            return self.create_backup(note="auto")
        else:
            logger.debug(f"Last backup is {age.total_seconds() / 3600:.1f}h old, no backup needed")
            return None


if __name__ == "__main__":
    # Test backup manager
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy database
        db_path = Path(tmpdir) / "test.db"
        db_path.write_text("Test database content")

        # Initialize backup manager
        manager = BackupManager(db_path, max_backups=3)

        print("Database Backup Manager Test")
        print("=" * 70)

        # Create backups
        print("\nCreating backups...")
        backup1 = manager.create_backup(compress=True, note="test1")
        backup2 = manager.create_backup(compress=False, note="test2")

        # List backups
        print("\nAvailable backups:")
        for backup in manager.list_backups():
            print(f"  {backup['name']}")
            print(f"    Size: {backup['size_bytes'] / 1024:.2f} KB")
            print(f"    Compressed: {backup['compressed']}")
            print(f"    Time: {backup['timestamp']}")

        # Verify
        print("\nVerifying backups...")
        for backup in manager.list_backups():
            valid = manager.verify_backup(backup["path"])
            print(f"  {backup['name']}: {'✓ Valid' if valid else '✗ Invalid'}")
