import ffmpeg
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioConverter:
    """Convert audio/video files to 16kHz mono WAV for whisper.cpp"""

    @staticmethod
    def convert_to_wav(input_path: str, output_path: str) -> None:
        """
        Convert any audio/video file to 16kHz mono WAV.

        Args:
            input_path: Path to input audio/video file
            output_path: Path to output WAV file

        Raises:
            Exception: If conversion fails
        """
        try:
            logger.info(f"Converting {input_path} to WAV format")

            # ffmpeg command: -ar 16000 (16kHz) -ac 1 (mono) -c:a pcm_s16le (16-bit PCM)
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                ar=16000,      # Sample rate: 16kHz
                ac=1,          # Channels: mono
                acodec='pcm_s16le',  # Codec: 16-bit PCM
                loglevel='error'
            )

            # Overwrite output file if exists
            stream = ffmpeg.overwrite_output(stream)

            # Run conversion
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)

            logger.info(f"Successfully converted to {output_path}")

        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg conversion failed: {error_msg}")
            raise Exception(f"Audio conversion failed: {error_msg}")

    @staticmethod
    def get_audio_duration(file_path: str) -> float:
        """
        Get duration of audio/video file in seconds.

        Args:
            file_path: Path to audio/video file

        Returns:
            Duration in seconds
        """
        try:
            probe = ffmpeg.probe(file_path)
            duration = float(probe['format']['duration'])
            return duration
        except Exception as e:
            logger.error(f"Failed to get duration: {e}")
            return 0.0
