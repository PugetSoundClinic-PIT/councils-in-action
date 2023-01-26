import logging
import re
from pathlib import Path

import dask.dataframe as dd
import pandas as pd
from cdp_backend.pipeline.transcript_model import Transcript
from cdp_data import CDPInstances, datasets
from dask import delayed
from distributed import Client, LocalCluster
from nltk.stem.snowball import SnowballStemmer
from sklearn.feature_extraction.text import CountVectorizer

###############################################################################

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)4s: %(module)s:%(lineno)4s %(asctime)s] %(message)s",
)
log = logging.getLogger(__name__)

###############################################################################

# CountVectorizer Setup
# Ignore numbers
def preprocess_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\d+", "", text)
    return text

# Construct custom count vectorizer
class StemmedCountVectorizer(CountVectorizer):
    def build_analyzer(self):
        analyzer = super(StemmedCountVectorizer, self).build_analyzer()
        stemmer = SnowballStemmer("english")
        return lambda doc: ([stemmer.stem(w) for w in analyzer(doc)])

# Init custom vectorizer
COUNT_VECTORIZER = StemmedCountVectorizer(
    stop_words="english",
    lowercase=True,
    preprocessor=preprocess_text,
    strip_accents="unicode",
)

# Dask delayed function to load transcript and get counts
@delayed
def get_word_count_df_for_each_transcript(row: pd.Series) -> pd.DataFrame:
    # Read transcript
    with open(row.transcript_path) as open_f:
        t = Transcript.from_json(open_f.read())
    
    # All content together
    try:
        this_transcript_counts = pd.DataFrame(
            COUNT_VECTORIZER.fit_transform(
                [" ".join([s.text for s in t.sentences])],
            ).toarray(),
            columns=COUNT_VECTORIZER.get_feature_names_out(),
        )
        this_transcript_counts = this_transcript_counts.melt(
            var_name="ngram",
            value_name="count_",
        )
        this_transcript_counts["percent_of_total"] = (
            this_transcript_counts.count_ / this_transcript_counts.count_.sum()
        )
        this_transcript_counts["session_datetime"] = row.session_datetime
        this_transcript_counts["council"] = row.council

    except ValueError:
        # Some error happened, just return empty dataframe
        # It will be swept away during concat
        this_transcript_counts = pd.DataFrame({
            "ngram": [],
            "count_": [],
            "percent_of_total": [],
            "session_datetime": [],
            "council": [],
        }).astype({
            "ngram": object,
            "session_datetime": "datetime64[ns, UTC]",
            "council": object,
        })

    return this_transcript_counts


###############################################################################

# Chunk filenaming and storage setup
def chunk_filenaming_func(x: int) -> str:
    return f"chunk-{x}.parquet"
OVERALL_DATASET_STORAGE_PATH = Path("councils-in-action-ds")
RAW_COUNTS_DATASET_STORAGE_PATH = OVERALL_DATASET_STORAGE_PATH / "raw-counts"

###############################################################################


def generate_datasets():
    # Setup parallel processing
    cluster = LocalCluster(
        processes=True,
        n_workers=2,
        threads_per_worker=2,
        memory_limit=0.3,
    )
    client = Client(cluster)
    log.info("-" * 80)
    log.info("Starting dataset generation.")
    log.info(f"Dask dashboard available at: {client.dashboard_link}")

    # Get instances data
    session_datasets = []
    for infra_slug in [
        CDPInstances.Seattle,
        CDPInstances.KingCounty,
        CDPInstances.LongBeach,
        CDPInstances.Oakland,
    ]:
        df = datasets.get_session_dataset(
            infra_slug,
            store_transcript=True,
            replace_py_objects=True,
            raise_on_error=False,
        )
        df["council"] = infra_slug
        session_datasets.append(df)

    # Concat
    all_sessions = pd.concat(session_datasets, ignore_index=True)
    log.info(
        f"Finished gathering transcript metadata dataset. "
        f"DataFrame shape: {all_sessions.shape}"
    )

    # Get dask.DataFrame from delayed pd.DataFrames
    session_df_rows = [row for _, row in all_sessions.iterrows()]
    counts_dfs = [get_word_count_df_for_each_transcript(row) for row in session_df_rows]

    # Concat and persist
    counts = dd.from_delayed(counts_dfs)
    counts = counts.persist()
    log.info("Read and processed all transcripts to raw counts.")

    # Store
    counts.to_parquet(
        str(RAW_COUNTS_DATASET_STORAGE_PATH),
        name_function=chunk_filenaming_func,
    )
    log.info(f"Stored raw ngram count data to: '{RAW_COUNTS_DATASET_STORAGE_PATH}'")

    # Make a bunch of rolling variations
    for rolling_window in [
        "7D",
        "14D",
        "30D",
    ]:
        # Compute rolling average over window
        rolled = counts.set_index(
            "session_datetime",
        ).groupby(
            ["council", "ngram"],
        ).rolling(
            rolling_window,
        ).mean().reset_index()
        
        # Store to parquet chunks
        store_dir = OVERALL_DATASET_STORAGE_PATH / f"rolling-{rolling_window.lower()}/"
        rolled.to_parquet(str(store_dir), name_function=chunk_filenaming_func)
        log.info(f"Stored {rolling_window} rolling average counts to: '{store_dir}'")


if __name__ == "__main__":
    generate_datasets()