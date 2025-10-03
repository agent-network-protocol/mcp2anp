"""MCP2ANP 主入口模块。"""

import click

from mcp2anp.server import main as local_main
from mcp2anp.server_remote import main as remote_main


@click.group()
def cli():
    """MCP2ANP 桥接服务器。"""
    pass


@cli.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="设置日志级别",
)
@click.option(
    "--reload",
    is_flag=True,
    help="启用开发热重载",
)
def local(log_level: str, reload: bool):
    """运行本地 stdio 模式服务器。"""
    local_main(log_level=log_level, reload=reload)


@cli.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="设置日志级别",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="服务器绑定地址",
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="服务器端口",
)
def remote(log_level: str, host: str, port: int):
    """运行远程 HTTP 模式服务器。"""
    remote_main(
        host=host,
        port=port,
        log_level=log_level
    )


if __name__ == "__main__":
    cli()