# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean CLI v1.0. Copyright 2021 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
from typing import Any, Dict

import click

from lean.click import PathParameter
from lean.container import container
from lean.models.errors import MoreInfoError


class LeanConfigConfigurer(abc.ABC):
    """The LeanConfigConfigurer class is the base class extended for all local brokerages and data feeds."""

    @classmethod
    @abc.abstractmethod
    def get_name(cls) -> str:
        """Returns the user-friendly name which users can identify this object by.

        :return: the user-friendly name to display to users
        """
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        """Configures the Lean configuration for this brokerage.

        If the Lean configuration has been configured for this brokerage before, nothing will be changed.

        :param lean_config: the configuration dict to write to
        :param environment_name: the name of the environment to configure
        """
        raise NotImplementedError()


class LocalBrokerage(LeanConfigConfigurer, abc.ABC):
    """The LocalBrokerage class is the base class extended for all local brokerages."""

    _credentials_configured = False

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        cls._configure_environment(lean_config, environment_name)
        cls.configure_credentials(lean_config)

    @classmethod
    def configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        if cls._credentials_configured:
            return

        cls._configure_credentials(lean_config)
        cls._credentials_configured = True

    @classmethod
    @abc.abstractmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        """Configures any required providers in the environments section of the Lean config.

        :param lean_config: the config dict to update
        :param environment_name: the name of the environment to update
        """
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        """Configures any required credentials in the Lean config.

        :param lean_config: the config dict to update
        """
        raise NotImplementedError()


class PaperTradingBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the paper trading brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Paper Trading"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "PaperBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        pass


class InteractiveBrokersBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Interactive Brokers brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Interactive Brokers"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "InteractiveBrokersBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        container.logger().info("""
To use IB with LEAN you must disable two-factor authentication or only use IBKR Mobile.
This is done from your IB Account Manage Account -> Settings -> User Settings -> Security -> Secure Login System.
In the Secure Login System, deselect all options or only select "IB Key Security via IBKR Mobile".
Interactive Brokers Lite accounts do not support API trading.
        """.strip())

        username = click.prompt("Username")
        account_id = click.prompt("Account id")
        account_password = click.prompt("Account password", hide_input=True)

        agent_description = None
        trading_mode = None

        demo_slice = account_id.lower()[:2]
        live_slice = account_id.lower()[0]

        if live_slice == "d":
            if demo_slice == "df" or demo_slice == "du":
                agent_description = "Individual"
                trading_mode = "paper"
            elif demo_slice == "di":
                # TODO: Set this to the correct value
                agent_description = "Advisor"
                trading_mode = "paper"
        else:
            if live_slice == "f" or live_slice == "i":
                agent_description = "Advisor"
                trading_mode = "live"
            elif live_slice == "u":
                # TODO: Set this to the correct value
                agent_description = "Individual"
                trading_mode = "live"

        if trading_mode is None:
            raise MoreInfoError(
                f"Account id '{account_id}' does not look like a valid account id",
                "https://www.lean.io/docs/lean-cli/tutorials/live-trading/local-live-trading#03-Interactive-Brokers"
            )

        lean_config["ib-user-name"] = username
        lean_config["ib-account"] = account_id
        lean_config["ib-passsword"] = account_password
        lean_config["ib-agent-description"] = agent_description
        lean_config["ib-trading-mode"] = trading_mode


class InteractiveBrokersDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the Interactive Brokers data feed."""

    @classmethod
    def get_name(cls) -> str:
        return InteractiveBrokersBrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = \
            "QuantConnect.Brokerages.InteractiveBrokers.InteractiveBrokersBrokerage"
        lean_config["environments"][environment_name]["history-provider"] = "BrokerageHistoryProvider"

        InteractiveBrokersBrokerage.configure_credentials(lean_config)

        container.logger().info("""
Delayed market data is used when you subscribe to data for which you don't have a market data subscription on IB.
If delayed market data is disabled, live trading will stop and LEAN will shut down when this happens.
        """.strip())

        lean_config["ib-enable-delayed-streaming-data"] = click.confirm("Enable delayed market data?")


class TradierBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Tradier brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Tradier"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "TradierBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        container.logger().info("""
Your Tradier account id and API token can be found on your Settings/API Access page (https://dash.tradier.com/settings/api).
The account id is the alpha-numeric code in a dropdown box on that page.
        """.strip())

        lean_config["tradier-account-id"] = click.prompt("Account id")
        lean_config["tradier-access-token"] = click.prompt("Access token", hide_input=True)
        lean_config["tradier-use-sandbox"] = click.confirm("Use the developer sandbox?")


class TradierDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the Tradier data feed."""

    @classmethod
    def get_name(cls) -> str:
        return TradierBrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = "TradierBrokerage"

        TradierBrokerage.configure_credentials(lean_config)


class OANDABrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the OANDA brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "OANDA"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "OandaBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        container.logger().info("""
Your OANDA account id can be found on your OANDA Account Statement page (https://www.oanda.com/account/statement/).
It follows the following format: ###-###-######-###.
You can generate an API token from the Manage API Access page (https://www.oanda.com/account/tpa/personal_token).
        """.strip())

        lean_config["oanda-account-id"] = click.prompt("Account id")
        lean_config["oanda-access-token"] = click.prompt("Access token", hide_input=True)

        environment = click.prompt("Environment", type=click.Choice(["real", "practice"], case_sensitive=False))
        lean_config["oanda-environment"] = "Trade" if environment == "real" else "Practice"


class OANDADataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the OANDA data feed."""

    @classmethod
    def get_name(cls) -> str:
        return OANDABrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = "OandaBrokerage"
        lean_config["environments"][environment_name]["history-provider"] = "BrokerageHistoryProvider"

        OANDABrokerage.configure_credentials(lean_config)


class CoinbaseProBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Coinbase Pro brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Coinbase Pro"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "GDAXBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        container.logger().info("""
You can generate Coinbase Pro API credentials on the API settings page (https://pro.coinbase.com/profile/api).
When creating the key, make sure you authorize it for View and Trading access.
        """.strip())

        lean_config["gdax-api-key"] = click.prompt("API key")
        lean_config["gdax-api-secret"] = click.prompt("API secret")
        lean_config["gdax-passphrase"] = click.prompt("Passphrase", hide_input=True)


class CoinbaseProDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the Coinbase Pro data feed."""

    @classmethod
    def get_name(cls) -> str:
        return CoinbaseProBrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = "GDAXDataQueueHandler"
        lean_config["environments"][environment_name]["history-provider"] = "BrokerageHistoryProvider"

        CoinbaseProBrokerage.configure_credentials(lean_config)


class BitfinexBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Bitfinex brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Bitfinex"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "BitfinexBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        container.logger().info("""
Create an API key by logging in and accessing the Bitfinex API Management page (https://www.bitfinex.com/api).
        """.strip())

        lean_config["bitfinex-api-key"] = click.prompt("API key")
        lean_config["bitfinex-api-secret"] = click.prompt("API secret")


class BitfinexDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the Bitfinex data feed."""

    @classmethod
    def get_name(cls) -> str:
        return BitfinexBrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = "BitfinexBrokerage"
        lean_config["environments"][environment_name]["history-provider"] = "BrokerageHistoryProvider"

        BitfinexBrokerage.configure_credentials(lean_config)


class BinanceBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Binance brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Binance"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "BinanceBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        container.logger().info("""
Create an API key by logging in and accessing the Bitfinex API Management page (https://www.bitfinex.com/api).
        """.strip())

        lean_config["binance-api-key"] = click.prompt("API key")
        lean_config["binance-api-secret"] = click.prompt("API secret")


class BinanceDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the Binance data feed."""

    @classmethod
    def get_name(cls) -> str:
        return BinanceBrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = "BinanceBrokerage"
        lean_config["environments"][environment_name]["history-provider"] = "BrokerageHistoryProvider"

        BinanceBrokerage.configure_credentials(lean_config)


class ZerodhaBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Zerodha brokerage."""

    @classmethod
    def get_name(cls) -> str:
        return "Zerodha"

    @classmethod
    def _configure_environment(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["live-mode-brokerage"] = "ZerodhaBrokerage"
        lean_config["environments"][environment_name]["transaction-handler"] = \
            "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler"

    @classmethod
    def _configure_credentials(cls, lean_config: Dict[str, Any]) -> None:
        logger = container.logger()

        logger.info("You need API credentials for Kite Connect (https://kite.trade/) to use the Zerodha brokerage.")

        lean_config["zerodha-api-key"] = click.prompt("API key")
        lean_config["zerodha-access-token"] = click.prompt("Access token")

        logger.info(
            "The product type must be set to MIS if you are targeting intraday products, CNC if you are targeting delivery products or NRML if you are targeting carry forward products.")

        lean_config["zerodha-product-type"] = click.prompt(
            "Product type",
            type=click.Choice(["MIS", "CNC", "NRML"], case_sensitive=False)
        )

        logger.info(
            "The trading segment must be set to EQUITY if you are trading equities on NSE or BSE, or COMMODITY if you are trading commodities on MCX.")

        lean_config["zerodha-trading-segment"] = click.prompt(
            "Trading segment",
            type=click.Choice(["EQUITY", "COMMODITY"], case_sensitive=False)
        )


class ZerodhaDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the Zerodha data feed."""

    @classmethod
    def get_name(cls) -> str:
        return ZerodhaBrokerage.get_name()

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = "ZerodhaBrokerage"
        lean_config["environments"][environment_name]["history-provider"] = "BrokerageHistoryProvider"

        ZerodhaBrokerage.configure_credentials(lean_config)

        lean_config["zerodha-history-subscription"] = click.confirm("Do you have a history API subscription?")


class IQFeedDataFeed(LeanConfigConfigurer):
    """A LeanConfigConfigurer implementation for the IQFeed data feed."""

    @classmethod
    def get_name(cls) -> str:
        return "IQFeed"

    @classmethod
    def configure(cls, lean_config: Dict[str, Any], environment_name: str) -> None:
        lean_config["environments"][environment_name]["data-queue-handler"] = \
            "QuantConnect.ToolBox.IQFeed.IQFeedDataQueueHandler"
        lean_config["environments"][environment_name]["history-provider"] = \
            "QuantConnect.ToolBox.IQFeed.IQFeedDataQueueHandler"

        container.logger().info(
            "The IQFeed data feed requires an IQFeed developer account a locally installed IQFeed client.")

        iqconnect_binary = click.prompt("IQConnect binary location",
                                        type=PathParameter(exists=True, file_okay=True, dir_okay=False))
        lean_config["iqfeed-iqconnect"] = str(iqconnect_binary)

        lean_config["iqfeed-username"] = click.prompt("Username")
        lean_config["iqfeed-password"] = click.prompt("Password")
        lean_config["iqfeed-productName"] = click.prompt("Product id")
        lean_config["iqfeed-version"] = click.prompt("Product version")


all_local_brokerages = [
    PaperTradingBrokerage,
    InteractiveBrokersBrokerage,
    TradierBrokerage,
    OANDABrokerage,
    CoinbaseProBrokerage,
    BitfinexBrokerage,
    BinanceBrokerage,
    ZerodhaBrokerage
]

local_brokerage_data_feeds = {
    PaperTradingBrokerage: [InteractiveBrokersDataFeed,
                            TradierDataFeed,
                            OANDADataFeed,
                            CoinbaseProDataFeed,
                            BitfinexDataFeed,
                            BinanceDataFeed,
                            ZerodhaDataFeed],
    InteractiveBrokersBrokerage: [InteractiveBrokersDataFeed],
    TradierBrokerage: [TradierDataFeed],
    OANDABrokerage: [OANDADataFeed],
    CoinbaseProBrokerage: [CoinbaseProDataFeed],
    BitfinexBrokerage: [BitfinexDataFeed],
    BinanceBrokerage: [BinanceDataFeed],
    ZerodhaBrokerage: [ZerodhaDataFeed]
}