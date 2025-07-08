import os
import json
import asyncpg
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.db_host = os.getenv("DB_HOST")
        self.db_port = int(os.getenv("DB_PORT", 5432))
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")
        self.db_ssl = os.getenv("DB_SSL", "require")
        
        if not all([self.db_host, self.db_name, self.db_user, self.db_password]):
            raise Exception("Database environment variables not set (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
        self.pool = None
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                ssl=self.db_ssl,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            print("Database connection pool initialized")
        except Exception as e:
            print(f"Failed to initialize database: {e}")
            raise e
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
    
    # User operations
    async def get_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT email, name, is_admin, created_at 
                FROM users 
                ORDER BY created_at
            """)
            return [dict(row) for row in rows]
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT email, name, is_admin, created_at 
                FROM users 
                WHERE email = $1
            """, email)
            return dict(row) if row else None
    
    async def create_user(self, email: str, name: str, is_admin: bool = False) -> bool:
        """Create new user"""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("""
                    INSERT INTO users (email, name, is_admin) 
                    VALUES ($1, $2, $3)
                """, email, name, is_admin)
                return True
        except asyncpg.UniqueViolationError:
            return False
        except Exception as e:
            print(f"Error creating user: {e}")
            return False
    
    async def delete_user(self, email: str) -> bool:
        """Delete user"""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.execute("""
                    DELETE FROM users WHERE email = $1
                """, email)
                return result == "DELETE 1"
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False
    
    # Deal operations
    async def get_deals(self) -> Dict[str, Any]:
        """Get all deals"""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT deal_id, amount, dealstage, dealtype, deal_stage_probability,
                       createdate, closedate, activities
                FROM deals
                ORDER BY deal_id
            """)
            
            deals = {}
            for row in rows:
                deal_data = dict(row)
                # Convert datetime objects to ISO strings
                if deal_data['createdate']:
                    deal_data['createdate'] = deal_data['createdate'].isoformat()
                if deal_data['closedate']:
                    deal_data['closedate'] = deal_data['closedate'].isoformat()
                
                deals[deal_data['deal_id']] = deal_data
            
            return deals
    
    async def get_deal_by_id(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get deal by deal_id"""
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT deal_id, amount, dealstage, dealtype, deal_stage_probability,
                       createdate, closedate, activities
                FROM deals
                WHERE deal_id = $1
            """, deal_id)
            
            if not row:
                return None
            
            deal_data = dict(row)
            # Convert datetime objects to ISO strings
            if deal_data['createdate']:
                deal_data['createdate'] = deal_data['createdate'].isoformat()
            if deal_data['closedate']:
                deal_data['closedate'] = deal_data['closedate'].isoformat()
            
            return deal_data
    
    async def create_deal(self, deal_data: Dict[str, Any]) -> bool:
        """Create new deal"""
        def parse_datetime(dt_str):
            if not dt_str:
                return None
            try:
                # Handle various datetime formats
                if isinstance(dt_str, str):
                    # Remove 'Z' and replace with +00:00 for proper ISO format
                    dt_str = dt_str.replace('Z', '+00:00')
                    # Parse the datetime
                    dt = datetime.fromisoformat(dt_str)
                    # Convert to naive datetime (remove timezone info completely)
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    return dt
                return dt_str
            except:
                # If parsing fails, try basic parsing without timezone
                try:
                    # Extract just the date and time part, ignore timezone
                    clean_str = dt_str.split('T')[0] + 'T' + dt_str.split('T')[1].split('+')[0].split('Z')[0].split('.')[0]
                    return datetime.fromisoformat(clean_str)
                except:
                    return None
        
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("""
                    INSERT INTO deals (deal_id, amount, dealstage, dealtype, 
                                    deal_stage_probability, createdate, closedate, activities)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, 
                deal_data['deal_id'],
                float(deal_data.get('amount', 0)) if deal_data.get('amount') else None,
                deal_data.get('dealstage'),
                deal_data.get('dealtype'),
                float(deal_data.get('deal_stage_probability', 0)) if deal_data.get('deal_stage_probability') else None,
                parse_datetime(deal_data.get('createdate')),
                parse_datetime(deal_data.get('closedate')),
                json.dumps(deal_data.get('activities', []))
                )
                return True
        except Exception as e:
            print(f"Error creating deal: {e}")
            return False
    
    # LLM output operations
    async def get_llm_outputs(self) -> Dict[str, Any]:
        """Get all LLM outputs"""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT deal_id, overall_sentiment, sentiment_score, confidence,
                       activity_breakdown, deal_momentum_indicators, reasoning,
                       professional_gaps, excellence_indicators, risk_indicators,
                       opportunity_indicators, temporal_trend, recommended_actions,
                       context_analysis_notes
                FROM llm_outputs
                ORDER BY deal_id
            """)
            
            outputs = {}
            for row in rows:
                output_data = dict(row)
                outputs[output_data['deal_id']] = output_data
            
            return outputs
    
    async def get_llm_output_by_deal_id(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get LLM output by deal_id"""
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT deal_id, overall_sentiment, sentiment_score, confidence,
                       activity_breakdown, deal_momentum_indicators, reasoning,
                       professional_gaps, excellence_indicators, risk_indicators,
                       opportunity_indicators, temporal_trend, recommended_actions,
                       context_analysis_notes
                FROM llm_outputs
                WHERE deal_id = $1
            """, deal_id)
            
            return dict(row) if row else None
    
    async def create_llm_output(self, deal_id: str, output_data: Dict[str, Any]) -> bool:
        """Create new LLM output"""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("""
                    INSERT INTO llm_outputs (
                        deal_id, overall_sentiment, sentiment_score, confidence,
                        activity_breakdown, deal_momentum_indicators, reasoning,
                        professional_gaps, excellence_indicators, risk_indicators,
                        opportunity_indicators, temporal_trend, recommended_actions,
                        context_analysis_notes
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                deal_id,
                output_data['overall_sentiment'],
                float(output_data['sentiment_score']),
                float(output_data['confidence']),
                json.dumps(output_data.get('activity_breakdown', {})),
                json.dumps(output_data.get('deal_momentum_indicators', {})),
                output_data.get('reasoning'),
                json.dumps(output_data.get('professional_gaps', [])),
                json.dumps(output_data.get('excellence_indicators', [])),
                json.dumps(output_data.get('risk_indicators', [])),
                json.dumps(output_data.get('opportunity_indicators', [])),
                output_data.get('temporal_trend'),
                json.dumps(output_data.get('recommended_actions', [])),
                json.dumps(output_data.get('context_analysis_notes', []))
                )
                return True
        except Exception as e:
            print(f"Error creating LLM output: {e}")
            return False
    
    # Annotation operations
    async def get_annotations(self) -> Dict[str, Any]:
        """Get all annotations grouped by deal_id and user_email"""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT deal_id, user_email, ratings, time_spent_seconds, created_at
                FROM annotations
                ORDER BY deal_id, user_email
            """)
            
            annotations = {}
            for row in rows:
                deal_id = row['deal_id']
                user_email = row['user_email']
                
                if deal_id not in annotations:
                    annotations[deal_id] = {}
                
                annotations[deal_id][user_email] = {
                    'user_email': user_email,
                    'timestamp': row['created_at'].isoformat(),
                    'ratings': row['ratings'],
                    'time_spent_seconds': row['time_spent_seconds']
                }
            
            return annotations
    
    async def get_user_annotations(self, user_email: str) -> List[str]:
        """Get list of deal_ids that user has annotated"""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT deal_id FROM annotations WHERE user_email = $1
            """, user_email)
            return [row['deal_id'] for row in rows]
    
    async def create_annotation(self, deal_id: str, user_email: str, 
                              ratings: Dict[str, Any], time_spent: int) -> bool:
        """Create new annotation"""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("""
                    INSERT INTO annotations (deal_id, user_email, ratings, time_spent_seconds)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (deal_id, user_email) 
                    DO UPDATE SET 
                        ratings = EXCLUDED.ratings,
                        time_spent_seconds = EXCLUDED.time_spent_seconds,
                        updated_at = CURRENT_TIMESTAMP
                """, deal_id, user_email, json.dumps(ratings), time_spent)
                return True
        except Exception as e:
            print(f"Error creating annotation: {e}")
            return False
    
    async def delete_user_annotations(self, user_email: str) -> bool:
        """Delete all annotations for a user"""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("""
                    DELETE FROM annotations WHERE user_email = $1
                """, user_email)
                return True
        except Exception as e:
            print(f"Error deleting user annotations: {e}")
            return False
    
    # Statistics and analytics
    async def get_annotation_counts_by_deal(self) -> Dict[str, int]:
        """Get count of annotations per deal"""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT deal_id, COUNT(*) as count
                FROM annotations
                GROUP BY deal_id
            """)
            return {row['deal_id']: row['count'] for row in rows}
    
    async def get_user_progress(self, user_email: str) -> Dict[str, Any]:
        """Get user's progress statistics"""
        async with self.pool.acquire() as connection:
            # Get completed deals for this user
            completed_deals = await connection.fetch("""
                SELECT deal_id FROM annotations WHERE user_email = $1
            """, user_email)
            
            # Get total deals count
            total_deals_row = await connection.fetchrow("""
                SELECT COUNT(*) as total FROM deals
            """)
            
            completed_count = len(completed_deals)
            total_deals = total_deals_row['total']
            
            return {
                'completed_count': completed_count,
                'total_deals': total_deals,
                'completed_deals': [row['deal_id'] for row in completed_deals]
            }
    
    async def get_admin_stats(self) -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        async with self.pool.acquire() as connection:
            # Get basic counts
            users_count = await connection.fetchval("SELECT COUNT(*) FROM users")
            deals_count = await connection.fetchval("SELECT COUNT(*) FROM deals")
            annotations_count = await connection.fetchval("SELECT COUNT(*) FROM annotations")
            
            # Get annotation counts per deal
            annotation_counts = await connection.fetch("""
                SELECT deal_id, COUNT(*) as count
                FROM annotations
                GROUP BY deal_id
            """)
            
            target_per_deal = 15  # TARGET_ANNOTATIONS_PER_DEAL
            completed_deals = sum(1 for row in annotation_counts if row['count'] >= target_per_deal)
            
            return {
                'total_users': users_count,
                'total_deals': deals_count,
                'total_annotations': annotations_count,
                'completed_deals': completed_deals,
                'target_annotations_per_deal': target_per_deal
            }
    
    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
                return True
        except:
            return False

# Global database manager instance
db_manager = DatabaseManager()