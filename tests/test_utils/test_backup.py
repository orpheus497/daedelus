"""Tests for backup module."""



def test_backup_creation(test_db, temp_dir):
    """Test backup creation."""
    from daedelus.utils.backup import create_backup

    test_db.log_command("test", "/home/user", 0, 0.01)
    backup_path = create_backup(test_db.db_path, temp_dir)
    assert backup_path.exists()


def test_backup_restoration(test_db, temp_dir):
    """Test backup restore."""
    from daedelus.utils.backup import create_backup, restore_backup

    test_db.log_command("test", "/home/user", 0, 0.01)
    backup_path = create_backup(test_db.db_path, temp_dir)
    restore_backup(backup_path, test_db.db_path)
    # Should restore successfully
    assert test_db.db_path.exists()
