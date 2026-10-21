Splitting it across three of you:

Person A: data pipeline. Merge the tracking files, flip every play to face the same direction, compute features per frame, then train a gradient-boosted model.
Person B: the play viewer, either Streamlit with Plotly animation or a small web app built with Kiro.
Person C: AWS setup, the Bedrock layer, the hit-exposure score, and the pitch.