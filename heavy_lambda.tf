variable "lambda_root" {
  type        = string
  description = "The relative path to the source of the lambda"
  default     = "heavy_lambda"
}

resource "null_resource" "install_dependencies" {
  provisioner "local-exec" {
    command = "pip install -r heavy_lambda/requirements.txt -t heavy_lambda/"
  }
  
  triggers = {
    dependencies_versions = filemd5("heavy_lambda/requirements.txt")
    source_versions = filemd5("heavy_lambda/index.py")
  }
}

resource "random_uuid" "lambda_src_hash" {
  keepers = {
    for filename in setunion(
      fileset(var.lambda_root, "index.py"),
      fileset(var.lambda_root, "requirements.txt")
    ):
        filename => filemd5("heavy_lambda/${filename}")
  }
}

data "archive_file" "lambda_source" {
  depends_on = [null_resource.install_dependencies]
  excludes   = [
    "__pycache__",
    "venv",
  ]

  source_dir  = var.lambda_root
  output_path = "${random_uuid.lambda_src_hash.result}.zip"
  type        = "zip"
}

resource "aws_lambda_function" "lambda" {
  function_name    = "my_function"
  filename         = data.archive_file.lambda_source.output_path
  source_code_hash = data.archive_file.lambda_source.output_base64sha256
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.10"

  environment {
    variables = {
      LOG_LEVEL = "DEBUG"
    }
  }
}