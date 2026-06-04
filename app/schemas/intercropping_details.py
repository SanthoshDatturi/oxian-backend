from typing import List

from pydantic import AliasChoices, BaseModel, Field


class SpecificArrangement(BaseModel):
    """Describes the specific arrangement for a single crop in an intercropping system."""

    crop_name: str = Field(description="Name of the crop as in the recommendation.")

    variety: str = Field(description="Variety of the crop as in the recommendation.")

    arrangement: str = Field(
        description="Spacing or pattern for this specific crop. E.g., '2 rows of beans between every 6 rows of maize'."
    )


class IntercroppingDetails(BaseModel):
    """Details specific to intercropping when a crop is part of an intercropping system."""

    id: str = Field(
        description="UUID of the intercropping.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )

    intercrop_type: str = Field(
        description="The type of intercropping (e.g., 'Row Intercropping')."
    )

    no_of_crops: int = Field(description="The number of different crops involved.")

    arrangement: str = Field(
        description="The overall spacing or pattern. E.g., '6 rows of maize followed by 2 rows of beans'."
    )

    specific_arrangement: List[SpecificArrangement] = Field(
        description="The arrangement details for each crop in the intercrop system."
    )

    benefits: List[str] = Field(
        description="A list of benefits for adopting this intercropping system."
    )
