"""
Athenaリポジトリ (AthenaRepository)
作成者: Lynn
----------------------------------
【役割】
Athenaデータベース（主にエラーログや履歴データ）へのデータアクセスを抽象化するクラスです。

【チームへのメリット】
1. 呼び出しの共通化: 
   サービス層はSQLの詳細を知る必要がなく、`get_active_errors_since(時刻)` を呼ぶだけで
   データが取得できます。
2. 保守性の向上: 
   もし取得元のテーブル名が変わったり、検索条件を微調整したくなった場合、
   このリポジトリ層（またはその下のSQLクラス）を修正するだけで済み、業務ロジックへの影響を最小限に抑えられます。
3. テストの容易性: 
   本物のDBを使わないユニットテストを行う際、このリポジトリを「偽物（Mock）」に差し替えることで、
   テストを高速かつ安定して実行できます。
"""

# app/infrastructure/repositories/athena_repository.py

class AthenaRepository:
    """
    Athena DBのデータ操作を管理するリポジトリです。
    実データ取得のロジックは注入された athena_sql オブジェクトに委譲します。
    """
    def __init__(self, athena_sql):
        """
        Args:
            athena_sql: Athena専用のSQL実行インスタンス
        """
        self._athena_sql = athena_sql

    def get_active_errors_since(self, rms_boot_ts: str):
        """
        指定された日時（RMS起動時など）以降に発生した、現在アクティブなエラーを取得します。
        
        Args:
            rms_boot_ts (str): 検索の起点となるタイムスタンプ（'YYYY-MM-DD HH:MM:SS'）
        Returns:
            list: エラー情報のリスト（AthenaSql.fetch_active_errors_since の戻り値）
        """
        # 下位層のSQL実行メソッドを呼び出し、結果をサービス層へ返します
        return self._athena_sql.fetch_active_errors_since(rms_boot_ts)