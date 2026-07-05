#!/usr/bin/env python3
"""
Script to apply database indexing strategy
Usage: python scripts/apply_database_indexes.py
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent.parent))

import logging

from app.core.config import settings
from app.db.indexing_strategy import get_index_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Apply database indexes"""
    print("🏗️  Starting Database Indexing Strategy Application")
    print(
        f"📊 Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'Local'}"
    )
    print("=" * 60)

    try:
        index_manager = get_index_manager()

        print("📈 Analyzing current index usage...")
        usage_stats = await index_manager.analyze_index_usage()

        if "error" not in usage_stats:
            print(f"📊 Found {len(usage_stats['index_usage'])} existing indexes")
            print(f"🗑️  Found {len(usage_stats['unused_indexes'])} unused indexes")

            # Show largest unused indexes
            if usage_stats["unused_indexes"]:
                print("\n⚠️  Largest unused indexes:")
                for idx in usage_stats["unused_indexes"][:5]:
                    print(
                        f"   - {idx['indexname']} on {idx['tablename']} ({idx['index_size']})"
                    )

        print("\n🔍 Getting slow query analysis...")
        slow_queries = await index_manager.get_slow_queries(5)
        if slow_queries:
            print(f"🐌 Found {len(slow_queries)} slow queries")
            for i, query in enumerate(slow_queries[:3], 1):
                print(
                    f"   {i}. Mean time: {query['mean_time']:.2f}ms, Calls: {query['calls']}"
                )
        else:
            print("   (pg_stat_statements extension not available)")

        print("\n💡 Generating index recommendations...")
        recommendations = await index_manager.recommend_indexes()
        if recommendations:
            print(f"📋 Found {len(recommendations)} recommendations:")
            for rec in recommendations:
                print(
                    f"   - {rec['type']}: {rec['table']}.{rec['column']} ({rec['priority']} priority)"
                )

        print("\n🚀 Creating optimized indexes...")
        results = await index_manager.create_all_indexes()

        # Report results
        print("\n✅ Successfully created:")
        print(f"   - {len(results['critical_indexes'])} critical indexes")
        print(f"   - {len(results['composite_indexes'])} composite indexes")
        print(f"   - {len(results['fulltext_indexes'])} full-text indexes")

        if results["errors"]:
            print("\n❌ Errors encountered:")
            for error in results["errors"]:
                print(f"   - {error}")

        print("\n📊 Index creation summary:")
        all_created = (
            results["critical_indexes"]
            + results["composite_indexes"]
            + results["fulltext_indexes"]
        )

        for idx in all_created:
            print(f"   ✓ {idx['name']}: {idx['description']}")

        print("\n🎉 Database indexing strategy applied successfully!")
        print(f"📈 Total indexes created: {len(all_created)}")

        if results["errors"]:
            print(
                f"⚠️  {len(results['errors'])} errors occurred - check logs for details"
            )
            return 1

        return 0

    except Exception as e:
        logger.error(f"Fatal error applying indexes: {str(e)}")
        print(f"\n💥 Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
